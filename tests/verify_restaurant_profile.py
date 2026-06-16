import os
import sys
import shutil

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_restaurant_profile.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

from backend.database.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.user_repository import UserRepository
from backend.services.auth_service import AuthService
from backend.services.restaurant_service import RestaurantService

def run_restaurant_profile_tests():
    print("=" * 80)
    print("RUNNING RESTAURANT PROFILE FOUNDATION VERIFICATION")
    print("=" * 80)

    # 1. Initialize test database
    print("Initializing test database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 2. Create test restaurants
        print("\nCreating test restaurants...")
        restaurant_a = RestaurantRepository.create(db, name="Restaurant Alpha")
        restaurant_b = RestaurantRepository.create(db, name="Restaurant Beta")
        
        # Create an inactive restaurant
        restaurant_inactive = RestaurantRepository.create(db, name="Restaurant Inactive")
        RestaurantRepository.update(db, restaurant_inactive.id, {"is_active": False})
        
        # Create a soft-deleted restaurant
        restaurant_deleted = RestaurantRepository.create(db, name="Restaurant Deleted")
        RestaurantRepository.soft_delete(db, restaurant_deleted.id)

        # 3. Create test users
        print("Creating test users...")
        admin_user = UserRepository.create(db, "admin@saas.com", "pass1234", UserRole.ADMIN)
        rest_a_user = UserRepository.create(
            db, "rest_a@saas.com", "pass1234", UserRole.RESTAURANT, restaurant_id=restaurant_a.id
        )
        rest_b_user = UserRepository.create(
            db, "rest_b@saas.com", "pass1234", UserRole.RESTAURANT, restaurant_id=restaurant_b.id
        )
        customer_user = UserRepository.create(db, "customer@saas.com", "pass1234", UserRole.CUSTOMER)

        # 4. Generate access tokens
        admin_token = AuthService.create_access_token(admin_user.id, admin_user.email, admin_user.role.value)
        rest_a_token = AuthService.create_access_token(rest_a_user.id, rest_a_user.email, rest_a_user.role.value)
        rest_b_token = AuthService.create_access_token(rest_b_user.id, rest_b_user.email, rest_b_user.role.value)
        customer_token = AuthService.create_access_token(customer_user.id, customer_user.email, customer_user.role.value)

        # =====================================================================
        # TEST 1: Profile Retrieval
        # =====================================================================
        print("\n1. Testing Profile Retrieval...")
        profile = RestaurantService.get_profile(db, rest_a_token, restaurant_a.id)
        assert profile.name == "Restaurant Alpha"
        assert profile.delivery_available is True
        print("✓ Profile retrieval succeeded.")

        # =====================================================================
        # TEST 2: Profile Updates (Restaurant User)
        # =====================================================================
        print("\n2. Testing Profile Updates...")
        update_data = {
            "name": "Restaurant Alpha Updated",
            "phone": "999-888-777",
            "address": "123 Main St",
            "description": "Premium pizza kitchen",
            "contact_email": "alpha_contact@saas.com",
            "delivery_available": True,
            "delivery_notes": "Deliver within 5km radius only."
        }
        updated = RestaurantService.update_profile(db, rest_a_token, restaurant_a.id, update_data)
        assert updated.name == "Restaurant Alpha Updated"
        # Wait, did it update the name?
        assert updated.phone == "999-888-777"
        assert updated.description == "Premium pizza kitchen"
        assert updated.contact_email == "alpha_contact@saas.com"
        assert updated.delivery_notes == "Deliver within 5km radius only."
        print("✓ Profile updates persisted successfully.")

        # =====================================================================
        # TEST 3: Admin Override
        # =====================================================================
        print("\n3. Testing Admin Override...")
        # Admin modifies Restaurant Alpha's details
        admin_update = {
            "description": "Admin description override",
            "phone": "111-222-333"
        }
        updated_by_admin = RestaurantService.update_profile(db, admin_token, restaurant_a.id, admin_update)
        assert updated_by_admin.description == "Admin description override"
        assert updated_by_admin.phone == "111-222-333"
        
        # Admin views Restaurant Alpha profile
        profile_by_admin = RestaurantService.get_profile(db, admin_token, restaurant_a.id)
        assert profile_by_admin.description == "Admin description override"
        print("✓ Admin override (both read and write) successfully verified.")

        # =====================================================================
        # TEST 4: Customer Access Denial
        # =====================================================================
        print("\n4. Testing Customer Denial...")
        try:
            RestaurantService.get_profile(db, customer_token, restaurant_a.id)
            assert False, "Failed: Customer was allowed to read restaurant profile"
        except PermissionError as e:
            assert "Customers cannot access restaurant resources" in str(e)
            
        try:
            RestaurantService.update_profile(db, customer_token, restaurant_a.id, {"phone": "000"})
            assert False, "Failed: Customer was allowed to update restaurant profile"
        except PermissionError as e:
            assert "Customers cannot access restaurant resources" in str(e)
        print("✓ Customer access denied on both read and write.")

        # =====================================================================
        # TEST 5: Active Restaurant Rejections
        # =====================================================================
        print("\n5. Testing Inactive & Soft-deleted Restaurant Rejections...")
        # Inactive restaurant
        try:
            RestaurantService.get_profile(db, admin_token, restaurant_inactive.id)
            assert False, "Failed: Inactive restaurant lookup should throw exception"
        except ValueError as e:
            assert "Restaurant is inactive or deleted" in str(e)

        try:
            RestaurantService.update_profile(db, admin_token, restaurant_inactive.id, {"phone": "000"})
            assert False, "Failed: Inactive restaurant update should throw exception"
        except ValueError as e:
            assert "Restaurant is inactive or deleted" in str(e)

        # Soft-deleted restaurant
        try:
            RestaurantService.get_profile(db, admin_token, restaurant_deleted.id)
            assert False, "Failed: Deleted restaurant lookup should throw exception"
        except ValueError as e:
            assert "Restaurant is inactive or deleted" in str(e)

        try:
            RestaurantService.update_profile(db, admin_token, restaurant_deleted.id, {"phone": "000"})
            assert False, "Failed: Deleted restaurant update should throw exception"
        except ValueError as e:
            assert "Restaurant is inactive or deleted" in str(e)
        print("✓ Inactive and soft-deleted restaurant protections verified.")

        # =====================================================================
        # TEST 6: Tenant Isolation
        # =====================================================================
        print("\n6. Testing Tenant Isolation...")
        # Restaurant A manager tries to access Restaurant B
        try:
            RestaurantService.get_profile(db, rest_a_token, restaurant_b.id)
            assert False, "Failed: Cross-tenant profile read was not blocked"
        except PermissionError as e:
            assert "Tenant isolation constraint violated" in str(e)

        try:
            RestaurantService.update_profile(db, rest_a_token, restaurant_b.id, {"phone": "444"})
            assert False, "Failed: Cross-tenant profile write was not blocked"
        except PermissionError as e:
            assert "Tenant isolation constraint violated" in str(e)
        print("✓ Tenant isolation boundaries validated.")

        # =====================================================================
        # TEST 7: Structured Business Hours
        # =====================================================================
        print("\n7. Testing Structured Business Hours...")
        # 7a. Valid structured hours (with open/close and closed properties)
        valid_hours = {
            "Monday": {"open": "08:00", "close": "22:00", "closed": False},
            "Tuesday": {"closed": True}  # open and close may be omitted
        }
        res_hours = RestaurantService.update_profile(db, rest_a_token, restaurant_a.id, {"business_hours": valid_hours})
        assert res_hours.business_hours["Monday"]["open"] == "08:00"
        assert res_hours.business_hours["Monday"]["close"] == "22:00"
        assert res_hours.business_hours["Monday"]["closed"] is False
        assert res_hours.business_hours["Tuesday"]["closed"] is True
        print("✓ Valid business hours mapping accepted.")

        # 7b. Invalid day keys
        invalid_day_hours = {
            "Funday": {"open": "09:00", "close": "17:00", "closed": False}
        }
        try:
            RestaurantService.update_profile(db, rest_a_token, restaurant_a.id, {"business_hours": invalid_day_hours})
            assert False, "Failed: Invalid day key was accepted"
        except ValueError as e:
            assert "Invalid day" in str(e)
            print("✓ Invalid weekday check correctly threw exception.")

        # 7c. Invalid time formats (e.g. HH:MM violation)
        invalid_time_hours_1 = {
            "Wednesday": {"open": "9:00", "close": "22:00", "closed": False}  # '9:00' instead of '09:00'
        }
        try:
            RestaurantService.update_profile(db, rest_a_token, restaurant_a.id, {"business_hours": invalid_time_hours_1})
            assert False, "Failed: Single digit hour format accepted"
        except ValueError as e:
            assert "HH:MM format" in str(e)
            print("✓ Invalid hour single-digit format correctly rejected.")

        invalid_time_hours_2 = {
            "Wednesday": {"open": "09:00", "close": "25:00", "closed": False}  # '25:00' is invalid hour
        }
        try:
            RestaurantService.update_profile(db, rest_a_token, restaurant_a.id, {"business_hours": invalid_time_hours_2})
            assert False, "Failed: Invalid hour bounds accepted"
        except ValueError as e:
            assert "HH:MM format" in str(e)
            print("✓ Out-of-bounds hour format correctly rejected.")

        # 7d. Missing times when closed=False
        missing_times_hours = {
            "Wednesday": {"closed": False}  # open and close missing when open
        }
        try:
            RestaurantService.update_profile(db, rest_a_token, restaurant_a.id, {"business_hours": missing_times_hours})
            assert False, "Failed: Missing hours on open day accepted"
        except ValueError as e:
            assert "required when restaurant is not closed" in str(e)
            print("✓ Missing times for open day correctly rejected.")

        # =====================================================================
        # TEST 8: Status Message Persistence
        # =====================================================================
        print("\n8. Testing Status Message Persistence...")
        updated_status = RestaurantService.update_profile(
            db, rest_a_token, restaurant_a.id, {"status_message": "Closed for Maintenance"}
        )
        assert updated_status.status_message == "Closed for Maintenance"
        
        fetched_status = RestaurantService.get_profile(db, rest_a_token, restaurant_a.id)
        assert fetched_status.status_message == "Closed for Maintenance"
        print("✓ Status message field successfully validated.")

    finally:
        db.close()
        # Clean up database file
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL RESTAURANT PROFILE VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_restaurant_profile_tests()
