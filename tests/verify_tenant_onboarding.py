import os
import sys

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_tenant_onboarding.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass

from backend.database.database import engine, Base, SessionLocal
from backend.models.user import UserRole
from backend.services.auth_service import AuthService
from backend.services.restaurant_service import RestaurantService
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.user_repository import UserRepository

def run_tenant_onboarding_tests():
    print("=" * 80)
    print("RUNNING TENANT ONBOARDING VERIFICATION")
    print("=" * 80)

    # 1. Initialize tables
    print("Initializing test database...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Assertion 1: Manager cannot register without tenant context
        print("\n1. Verifying that a manager cannot register without tenant context...")
        
        # Test 1.a: Through AuthService.register_user directly
        try:
            AuthService.register_user(
                db=db,
                email="manager_orphan_auth@saas.com",
                password_raw="securepass123",
                role=UserRole.RESTAURANT
            )
            assert False, "Failed: AuthService allowed manager registration without tenant context"
        except ValueError as e:
            print(f"✓ AuthService.register_user rejected orphan manager as expected: {e}")

        # Test 1.b: Through RestaurantService.onboard_restaurant with both None
        try:
            RestaurantService.onboard_restaurant(
                db=db,
                email="manager_orphan_service@saas.com",
                password_raw="securepass123",
                first_name="Orphan",
                last_name="Manager",
                restaurant_name=None,
                existing_restaurant_id=None
            )
            assert False, "Failed: RestaurantService allowed manager onboarding without any tenant context"
        except ValueError as e:
            print(f"✓ RestaurantService.onboard_restaurant rejected empty context: {e}")


        # Assertion 2: Existing restaurant mapping succeeds
        print("\n2. Verifying existing restaurant mapping...")
        # Create an existing restaurant beforehand
        existing_rest = RestaurantRepository.create(db=db, name="Tasty Treats Cafe")
        assert existing_rest.id is not None
        
        created_rest, user = RestaurantService.onboard_restaurant(
            db=db,
            email="manager_existing@saas.com",
            password_raw="securepass123",
            first_name="Alice",
            last_name="Smith",
            restaurant_name=None,
            existing_restaurant_id=existing_rest.id
        )
        
        # Alice is mapped to the existing restaurant
        assert user.role == UserRole.RESTAURANT
        assert user.restaurant_id == existing_rest.id
        # Since it was existing, onboard_restaurant should return None or the existing rest.
        # Let's check what the service returns. In our service:
        # created_restaurant is None for existing, so it returns None, user (or existing, user depending on return value)
        # Wait, in the repository diff, it returned created_restaurant, user, so created_restaurant is None for existing.
        assert user.email == "manager_existing@saas.com"
        print("✓ Existing restaurant mapping succeeded.")


        # Assertion 3: New restaurant onboarding succeeds
        print("\n3. Verifying new restaurant onboarding...")
        new_rest, manager_user = RestaurantService.onboard_restaurant(
            db=db,
            email="manager_new@saas.com",
            password_raw="securepass123",
            first_name="Bob",
            last_name="Jones",
            restaurant_name="Gourmet Pizza Hub",
            existing_restaurant_id=None
        )
        
        assert new_rest is not None
        assert new_rest.name == "Gourmet Pizza Hub"
        assert manager_user.role == UserRole.RESTAURANT
        assert manager_user.restaurant_id == new_rest.id
        print("✓ New restaurant onboarding succeeded.")


        # Assertion 4: Duplicate restaurant name fails
        print("\n4. Verifying duplicate restaurant name rejection...")
        try:
            RestaurantService.onboard_restaurant(
                db=db,
                email="manager_dup@saas.com",
                password_raw="securepass123",
                first_name="Charlie",
                last_name="Brown",
                restaurant_name="Gourmet Pizza Hub",  # Duplicate name
                existing_restaurant_id=None
            )
            assert False, "Failed: Allowed duplicate restaurant name creation"
        except ValueError as e:
            assert "already taken" in str(e) or "already registered" in str(e)
            print(f"✓ Duplicate restaurant name rejected: {e}")


        # Assertion 5: Transaction rollback occurs if manager creation fails
        print("\n5. Verifying transaction rollback on manager creation failure...")
        # We will trigger user creation failure by using an already registered email: manager_new@saas.com
        target_name = "Failure Diner"
        try:
            RestaurantService.onboard_restaurant(
                db=db,
                email="manager_new@saas.com", # Duplicate email, will fail user creation
                password_raw="securepass123",
                first_name="Failure",
                last_name="Manager",
                restaurant_name=target_name,
                existing_restaurant_id=None
            )
            assert False, "Failed: Allowed onboarding with duplicate email"
        except ValueError as e:
            assert "Email already registered" in str(e)
            print(f"✓ Manager creation failed as expected: {e}")
            
        # Verify that "Failure Diner" was rolled back and does not exist in db
        rolled_back_rest = RestaurantRepository.get_by_name(db=db, name=target_name)
        assert rolled_back_rest is None, "Failed: 'Failure Diner' was not rolled back and persists in DB"
        print("✓ New restaurant creation rolled back cleanly.")


        # Assertion 6: Customer registration remains unchanged
        print("\n6. Verifying customer registration remains unchanged...")
        customer_user = AuthService.register_user(
            db=db,
            email="customer@saas.com",
            password_raw="securepass123",
            role=UserRole.CUSTOMER,
            first_name="John",
            last_name="Doe"
        )
        assert customer_user.id is not None
        assert customer_user.role == UserRole.CUSTOMER
        assert customer_user.restaurant_id is None
        print("✓ Customer registered successfully without restaurant mapping.")


        # Assertion 7: Admin registration remains unchanged
        print("\n7. Verifying admin registration remains unchanged...")
        admin_user = AuthService.register_user(
            db=db,
            email="admin@saas.com",
            password_raw="securepass123",
            role=UserRole.ADMIN,
            first_name="Super",
            last_name="User"
        )
        assert admin_user.id is not None
        assert admin_user.role == UserRole.ADMIN
        assert admin_user.restaurant_id is None
        print("✓ Admin registered successfully without restaurant mapping.")

    finally:
        db.close()
        # Clean up database file
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass

    print("\n✓ ALL TENANT ONBOARDING VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_tenant_onboarding_tests()
