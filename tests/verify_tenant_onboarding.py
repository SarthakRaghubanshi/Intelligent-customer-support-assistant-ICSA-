import os
import sys
import shutil

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
    print("RUNNING TENANT ONBOARDING VERIFICATION (FINAL ARCHITECTURE)")
    print("=" * 80)

    # 1. Initialize tables
    print("Initializing test database...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Create a seeded restaurant and an admin/manager for invitation testing
        print("\nSeeding baseline restaurant and admin...")
        seeded_rest = RestaurantRepository.create(db=db, name="Seeded Cafe")
        
        seeded_admin = UserRepository.create(
            db=db,
            email="admin@saas.com",
            password_raw="securepass123",
            role=UserRole.ADMIN
        )
        # Create token for administrative calls
        admin_token = AuthService.create_access_token(seeded_admin.id, seeded_admin.email, seeded_admin.role.value)

        # =====================================================================
        # TEST 1: New Restaurant Manager Onboarding (PASS expected)
        # =====================================================================
        print("\nTest 1: Verifying new restaurant manager onboarding through AuthService...")
        manager_user = AuthService.register_user(
            db=db,
            email="manager_new@saas.com",
            password_raw="securepass123",
            role=UserRole.RESTAURANT,
            first_name="Bob",
            last_name="Jones",
            restaurant_name="Gourmet Pizza Hub"
        )
        
        assert manager_user.id is not None
        assert manager_user.role == UserRole.RESTAURANT
        assert manager_user.restaurant_id is not None
        
        # Verify restaurant was created
        new_rest = RestaurantRepository.get_by_id(db, manager_user.restaurant_id)
        assert new_rest is not None
        assert new_rest.name == "Gourmet Pizza Hub"
        print("✓ New restaurant manager onboarding succeeded.")

        # =====================================================================
        # TEST 2: Duplicate Restaurant Name Rejection (FAIL expected)
        # =====================================================================
        print("\nTest 2: Verifying duplicate restaurant name rejection...")
        try:
            AuthService.register_user(
                db=db,
                email="manager_dup_name@saas.com",
                password_raw="securepass123",
                role=UserRole.RESTAURANT,
                first_name="Charlie",
                last_name="Brown",
                restaurant_name="Gourmet Pizza Hub" # Duplicate name
            )
            assert False, "Failed: Allowed duplicate restaurant name registration"
        except ValueError as e:
            assert "already taken" in str(e)
            print(f"✓ Duplicate restaurant name rejected correctly: {e}")

        # =====================================================================
        # TEST 3: Duplicate Email Rejection (FAIL expected)
        # =====================================================================
        print("\nTest 3: Verifying duplicate email rejection...")
        try:
            AuthService.register_user(
                db=db,
                email="manager_new@saas.com", # Duplicate email
                password_raw="securepass123",
                role=UserRole.RESTAURANT,
                first_name="David",
                last_name="Miller",
                restaurant_name="Miller Bistro"
            )
            assert False, "Failed: Allowed registration with duplicate email"
        except ValueError as e:
            assert "Email already registered" in str(e)
            print(f"✓ Duplicate email rejected correctly: {e}")

        # =====================================================================
        # TEST 4: Atomicity & Rollback (PASS expected)
        # =====================================================================
        print("\nTest 4: Verifying rollback on manager creation failure...")
        target_name = "Failure Diner"
        try:
            AuthService.register_user(
                db=db,
                email="manager_new@saas.com", # Duplicate email, will fail user save step
                password_raw="securepass123",
                role=UserRole.RESTAURANT,
                first_name="Failure",
                last_name="Manager",
                restaurant_name=target_name
            )
            assert False, "Failed: Allowed onboarding with duplicate email"
        except ValueError as e:
            assert "Email already registered" in str(e)
            print(f"✓ Registration failed as expected: {e}")
            
        # Verify that "Failure Diner" was rolled back and does not exist in DB
        rolled_back_rest = RestaurantRepository.get_by_name(db=db, name=target_name)
        assert rolled_back_rest is None, "Failed: 'Failure Diner' was not rolled back and persists in DB"
        print("✓ New restaurant creation rolled back cleanly, database remains clean.")

        # =====================================================================
        # TEST 5: Public Existing Restaurant Joining Rejection (FAIL expected)
        # =====================================================================
        print("\nTest 5: Verifying public registration cannot join an existing restaurant...")
        try:
            AuthService.register_user(
                db=db,
                email="hacker@saas.com",
                password_raw="securepass123",
                role=UserRole.RESTAURANT,
                first_name="Hacker",
                last_name="One",
                restaurant_name=None,
                existing_restaurant_id=seeded_rest.id # Injection of existing id
            )
            assert False, "Failed: Allowed public registration to link to existing restaurant ID"
        except PermissionError as e:
            assert "cannot join an existing restaurant" in str(e)
            print(f"✓ Injected existing_restaurant_id was rejected as expected: {e}")

        # =====================================================================
        # TEST 6: Customer Registration Unchanged (PASS expected)
        # =====================================================================
        print("\nTest 6: Verifying customer registration remains unchanged...")
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
        print("✓ Customer registered successfully without restaurant context.")

        # =====================================================================
        # TEST 7: Admin Registration Unchanged (PASS expected)
        # =====================================================================
        print("\nTest 7: Verifying admin registration remains unchanged...")
        admin_user = AuthService.register_user(
            db=db,
            email="admin_new@saas.com",
            password_raw="securepass123",
            role=UserRole.ADMIN,
            first_name="Super",
            last_name="User"
        )
        assert admin_user.id is not None
        assert admin_user.role == UserRole.ADMIN
        assert admin_user.restaurant_id is None
        print("✓ Admin registered successfully without restaurant context.")

        # =====================================================================
        # TEST 8: Internal Manager Onboarding via invite_manager (PASS expected)
        # =====================================================================
        print("\nTest 8: Verifying authorized invite_manager linking...")
        linked_rest, linked_user = RestaurantService.invite_manager(
            db=db,
            token=admin_token,
            email="manager_invite@saas.com",
            password_raw="securepass123",
            first_name="Invited",
            last_name="Manager",
            existing_restaurant_id=seeded_rest.id
        )
        assert linked_rest.id == seeded_rest.id
        assert linked_user.role == UserRole.RESTAURANT
        assert linked_user.restaurant_id == seeded_rest.id
        print("✓ Internal manager invitation linked manager to existing restaurant successfully.")

        # =====================================================================
        # TEST 9: Unauthorized invite_manager Call Rejection (FAIL expected)
        # =====================================================================
        print("\nTest 9: Verifying unauthorized invite_manager call gets blocked...")
        # Create token for regular customer
        customer_token = AuthService.create_access_token(customer_user.id, customer_user.email, customer_user.role.value)
        try:
            RestaurantService.invite_manager(
                db=db,
                token=customer_token,
                email="manager_hack@saas.com",
                password_raw="securepass123",
                first_name="Hack",
                last_name="Manager",
                existing_restaurant_id=seeded_rest.id
            )
            assert False, "Failed: Allowed regular customer token to execute manager invitation"
        except PermissionError as e:
            assert "Denied" in str(e)
            print(f"✓ Unauthorized call blocked with PermissionError as expected: {e}")

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
