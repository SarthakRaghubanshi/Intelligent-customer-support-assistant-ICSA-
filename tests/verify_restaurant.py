import os
import sys
from sqlalchemy.exc import IntegrityError

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_restaurant_saas.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

from backend.database.database import engine, Base, SessionLocal
from backend.models.restaurant import Restaurant
from backend.models.user import User, UserRole
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.user_repository import UserRepository

def run_restaurant_tests():
    print("=" * 80)
    print("RUNNING RESTAURANT MANAGEMENT FOUNDATION VERIFICATION")
    print("=" * 80)

    # 1. Initialize test database
    print("Initializing test database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 2. Test Restaurant Creation
        print("\n1. Testing Restaurant Creation...")
        name = "Bella Italia"
        phone = "+39 06 1234567"
        address = "Via Condotti, 10, Rome, Italy"
        description = "Authentic Italian cuisine in the heart of Rome."

        restaurant = RestaurantRepository.create(
            db=db,
            name=name,
            phone=phone,
            address=address,
            description=description
        )

        assert restaurant.id is not None
        assert restaurant.name == name
        assert restaurant.phone == phone
        assert restaurant.address == address
        assert restaurant.description == description
        assert restaurant.is_active is True
        assert restaurant.deleted_at is None
        print("✓ Restaurant created successfully.")

        # Test duplicate name constraint
        print("\n2. Testing Unique Name Constraint...")
        try:
            RestaurantRepository.create(db=db, name=name)
            assert False, "Failed: Allowed duplicate restaurant name registration"
        except IntegrityError:
            db.rollback()
            print("✓ Duplicate name registration rejected by database constraint correctly.")

        # 3. Test Retrieval by Name and ID
        print("\n3. Testing Retrieval Operations...")
        retrieved_by_id = RestaurantRepository.get_by_id(db, restaurant.id)
        assert retrieved_by_id is not None
        assert retrieved_by_id.name == name

        retrieved_by_name = RestaurantRepository.get_by_name(db, name)
        assert retrieved_by_name is not None
        assert retrieved_by_name.id == restaurant.id

        # Verify case-insensitivity
        retrieved_case_insensitive = RestaurantRepository.get_by_name(db, "   BELLA ITALIA  ")
        assert retrieved_case_insensitive is not None
        assert retrieved_case_insensitive.id == restaurant.id
        print("✓ Retrieval by ID, exact name, and case-insensitive name works.")

        # 4. Test Update Operations
        print("\n4. Testing Update Operations...")
        updated_dict = {
            "phone": "+39 06 7654321",
            "description": "Updated Description"
        }
        updated = RestaurantRepository.update(db, restaurant.id, updated_dict)
        assert updated is not None
        assert updated.phone == "+39 06 7654321"
        assert updated.description == "Updated Description"
        print("✓ Restaurant fields updated successfully.")

        # 5. Test One-to-Many Relationship Mapping
        print("\n5. Testing Restaurant (1) -> Many Users relationship mapping...")
        user1 = UserRepository.create(
            db=db,
            email="manager1@restaurant.com",
            password_raw="managerpass123",
            role=UserRole.RESTAURANT,
            first_name="Marco",
            last_name="Rossi",
            restaurant_id=restaurant.id
        )
        user2 = UserRepository.create(
            db=db,
            email="staff1@restaurant.com",
            password_raw="staffpass123",
            role=UserRole.RESTAURANT,
            first_name="Giulia",
            last_name="Bianchi",
            restaurant_id=restaurant.id
        )

        db.refresh(restaurant)
        # Assert relationships load correctly
        assert user1.restaurant_id == restaurant.id
        assert user1.restaurant.id == restaurant.id
        assert user2.restaurant.id == restaurant.id
        
        assert len(restaurant.users) == 2
        user_ids_in_restaurant = [u.id for u in restaurant.users]
        assert user1.id in user_ids_in_restaurant
        assert user2.id in user_ids_in_restaurant
        print("✓ Users correctly link to Restaurant and Restaurant.users displays all linked members.")

        # 6. Test Soft Delete behavior
        print("\n6. Testing Soft Delete & Query Isolation...")
        deleted = RestaurantRepository.soft_delete(db, restaurant.id)
        assert deleted is True

        # Assert lookups return None for soft-deleted restaurants
        retrieved_after_delete = RestaurantRepository.get_by_id(db, restaurant.id)
        assert retrieved_after_delete is None

        retrieved_name_after_delete = RestaurantRepository.get_by_name(db, name)
        assert retrieved_name_after_delete is None

        # Verify active list omits it
        active_list = RestaurantRepository.list_active(db)
        assert len(active_list) == 0

        # Assert physical record still exists in the database
        raw_record = db.query(Restaurant).filter(Restaurant.id == restaurant.id).first()
        assert raw_record is not None
        assert raw_record.deleted_at is not None
        print("✓ Soft delete flags are set correctly, and queries filter out deleted restaurants by default.")

    finally:
        db.close()
        # Clean up database file
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL RESTAURANT MANAGEMENT FOUNDATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_restaurant_tests()
