import os
import sys
import re
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force SQLite in-memory or a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_saas.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

from backend.database.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.repositories.user_repository import UserRepository
from backend.core.security import verify_password
from backend.schemas.user_schema import UserCreate, UserResponse, UserUpdate

# Regex to validate standard UUIDv4 format
UUID_V4_REGEX = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$', re.I)

def run_tests():
    print("=" * 80)
    print("RUNNING FOUNDATIONAL USER MODEL VERIFICATION")
    print("=" * 80)

    # 1. Initialize fresh schema tables
    print("Initializing test database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 2. Test User Creation & Password Hashing
        print("Testing User creation and validation...")
        
        # Admin User Creation
        admin_raw = {
            "email": "admin@saas.com",
            "password": "secureadminpass123",
            "role": UserRole.ADMIN,
            "first_name": "SaaS",
            "last_name": "Admin"
        }
        # Validate input with Pydantic
        admin_schema = UserCreate(**admin_raw)
        
        admin_db = UserRepository.create(
            db=db,
            email=admin_schema.email,
            password_raw=admin_schema.password,
            role=admin_schema.role,
            first_name=admin_schema.first_name,
            last_name=admin_schema.last_name
        )
        assert admin_db.id is not None, "Failed: Admin ID not generated"
        
        # 2.1 UUID Verification
        assert UUID_V4_REGEX.match(admin_db.id), f"Failed: Generated ID {admin_db.id} is not a valid UUIDv4 string"
        print("✓ UUIDv4 generation format verified.")
        
        assert admin_db.email == "admin@saas.com", f"Failed: Email mismatch, got {admin_db.email}"
        assert admin_db.role == UserRole.ADMIN, "Failed: Role mismatch"
        assert verify_password("secureadminpass123", admin_db.hashed_password), "Failed: Hashed password verification failed"
        assert admin_db.is_active is True, "Failed: default is_active not True"
        assert admin_db.deleted_at is None, "Failed: deleted_at initially set"
        print("✓ Admin User successfully created with secure bcrypt hashing.")

        # Customer User Creation
        customer_raw = {
            "email": "customer@client.com",
            "password": "clientsecretpass",
            "role": UserRole.CUSTOMER
        }
        customer_schema = UserCreate(**customer_raw)
        customer_db = UserRepository.create(
            db=db,
            email=customer_schema.email,
            password_raw=customer_schema.password,
            role=customer_schema.role
        )
        assert customer_db.id is not None
        assert customer_db.role == UserRole.CUSTOMER
        print("✓ Customer User successfully created.")

        # 2.2 Role Validation Checks
        print("Testing Role validation constraints...")
        try:
            # Attempt schema validation with invalid role
            invalid_role_raw = {
                "email": "badrole@test.com",
                "password": "somepassval123",
                "role": "moderator"  # Invalid role
            }
            UserCreate(**invalid_role_raw)
            assert False, "Failed: Pydantic allowed invalid UserRole"
        except ValidationError:
            print("✓ Role validation constraint correctly caught by Pydantic.")

        # 3. Test Retrieval
        print("Testing retrieval by ID and Email...")
        retrieved_by_id = UserRepository.get_by_id(db, admin_db.id)
        assert retrieved_by_id is not None
        assert retrieved_by_id.email == "admin@saas.com"

        retrieved_by_email = UserRepository.get_by_email(db, "customer@client.com")
        assert retrieved_by_email is not None
        assert retrieved_by_email.id == customer_db.id
        print("✓ User retrieval functions correct.")

        # 4. Test Unique Constraint Validation (Email Uniqueness)
        print("Testing Unique constraint mapping on email...")
        try:
            UserRepository.create(db=db, email="admin@saas.com", password_raw="somepass", role=UserRole.CUSTOMER)
            assert False, "Failed: Allowed duplicate email creation"
        except IntegrityError:
            db.rollback()
            print("✓ Database unique constraints correctly enforced.")

        # 5. Test Update and password re-hashing (UserUpdate Validation)
        print("Testing UserUpdate schema validation...")
        update_data = {"email": "updatedemail@test.com", "password": "newsupersecretpass"}
        update_schema = UserUpdate(**update_data)
        assert update_schema.email == "updatedemail@test.com"
        assert update_schema.password == "newsupersecretpass"
        
        try:
            UserUpdate(email="bademailaddress")
            assert False, "Failed: Allowed invalid email in UserUpdate"
        except ValidationError:
            print("✓ UserUpdate schema validation constraints verified.")

        print("Testing record database modification...")
        updated_user = UserRepository.update(db, customer_db.id, update_schema.model_dump(exclude_unset=True))
        assert updated_user is not None
        assert updated_user.email == "updatedemail@test.com"
        assert verify_password("newsupersecretpass", updated_user.hashed_password)
        assert not verify_password("clientsecretpass", updated_user.hashed_password)
        print("✓ User updates and password re-hashing verified successfully.")

        # 6. Test Soft Delete
        print("Testing soft delete behavior...")
        delete_success = UserRepository.soft_delete(db, customer_db.id)
        assert delete_success is True, "Failed: soft_delete returned False"
        
        # Check that direct queries for active users now return None
        inactive_by_id = UserRepository.get_by_id(db, customer_db.id)
        assert inactive_by_id is None, "Failed: soft-deleted user still retrievable via get_by_id"
        
        inactive_by_email = UserRepository.get_by_email(db, "updatedemail@test.com")
        assert inactive_by_email is None, "Failed: soft-deleted user still retrievable via get_by_email"
        
        # Assert the record still physically exists in DB with a deleted_at timestamp
        raw_db_record = db.query(User).filter(User.id == customer_db.id).first()
        assert raw_db_record is not None, "Failed: Soft delete deleted physical DB record"
        assert raw_db_record.deleted_at is not None, "Failed: soft-deleted record deleted_at timestamp not set"
        print("✓ Soft deletion behavior and timestamps verified.")

        # 7. Validate schema serializers
        print("Testing response model serialization...")
        response_model = UserResponse.model_validate(admin_db)
        assert response_model.email == "admin@saas.com"
        assert response_model.role == UserRole.ADMIN
        print("✓ Pydantic validation mapping verified.")

    finally:
        db.close()
        # Clean up database file
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL FOUNDATIONAL USER MODEL VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_tests()
