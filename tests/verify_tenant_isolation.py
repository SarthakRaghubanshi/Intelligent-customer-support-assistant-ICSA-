import os
import sys

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_tenant_saas_isolation.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

# Mock streamlit before imports that might check it
import streamlit as st
if "is_authenticated" not in st.session_state:
    st.session_state.is_authenticated = False
if "user" not in st.session_state:
    st.session_state.user = None
if "active_view" not in st.session_state:
    st.session_state.active_view = None
if "selected_restaurant" not in st.session_state:
    st.session_state.selected_restaurant = None

# Stub streamlit functions to prevent errors during bare python test runs
st.rerun = lambda: None
st.warning = lambda msg: None

from backend.database.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.models.restaurant import Restaurant
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.user_repository import UserRepository
from backend.core.tenant import verify_tenant_access, verify_restaurant_active
from backend.services.auth_service import AuthService
from frontend.utils.auth_helper import init_landing_view, check_auth

def run_tenant_isolation_tests():
    print("=" * 80)
    print("RUNNING TENANT ISOLATION FOUNDATION VERIFICATION")
    print("=" * 80)

    # 1. Initialize test database
    print("Initializing test database tables...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 2. Create test restaurants
        print("\nCreating test restaurants...")
        restaurant_a = RestaurantRepository.create(db, name="Restaurant A")
        restaurant_b = RestaurantRepository.create(db, name="Restaurant B")
        
        # Soft-deleted restaurant
        restaurant_deleted = RestaurantRepository.create(db, name="Soft Deleted Restaurant")
        RestaurantRepository.soft_delete(db, restaurant_deleted.id)
        
        # Inactive restaurant
        restaurant_inactive = Restaurant(name="Inactive Restaurant", is_active=False)
        db.add(restaurant_inactive)
        db.commit()
        db.refresh(restaurant_inactive)

        # 3. Create test users
        print("\nCreating test users...")
        admin_user = UserRepository.create(db, "admin@saas.com", "pass1234", UserRole.ADMIN)
        rest_a_user = UserRepository.create(
            db, "rest_a@saas.com", "pass1234", UserRole.RESTAURANT, restaurant_id=restaurant_a.id
        )
        rest_b_user = UserRepository.create(
            db, "rest_b@saas.com", "pass1234", UserRole.RESTAURANT, restaurant_id=restaurant_b.id
        )
        customer_user = UserRepository.create(db, "customer@saas.com", "pass1234", UserRole.CUSTOMER)

        # 4. Generate token credentials
        admin_token = AuthService.create_access_token(admin_user.id, admin_user.email, admin_user.role.value)
        rest_a_token = AuthService.create_access_token(rest_a_user.id, rest_a_user.email, rest_a_user.role.value)
        rest_b_token = AuthService.create_access_token(rest_b_user.id, rest_b_user.email, rest_b_user.role.value)
        customer_token = AuthService.create_access_token(customer_user.id, customer_user.email, customer_user.role.value)

        # 5. Verify verify_tenant_access
        print("\n1. Testing verify_tenant_access function rules...")
        
        # Restaurant A accessing Restaurant A -> Allowed
        verify_tenant_access(rest_a_user, restaurant_a.id)
        print("✓ Restaurant A user allowed to access Restaurant A.")

        # Restaurant A accessing Restaurant B -> Blocked
        try:
            verify_tenant_access(rest_a_user, restaurant_b.id)
            assert False, "Failed: Restaurant A user was allowed to access Restaurant B"
        except PermissionError as e:
            print(f"✓ Cross-tenant access rejected as expected: {e}")

        # Admin accessing any restaurant -> Allowed (Admin override support)
        verify_tenant_access(admin_user, restaurant_a.id)
        verify_tenant_access(admin_user, restaurant_b.id)
        print("✓ Admin override verified: Admin user allowed to access all restaurants.")

        # Customer accessing restaurant resources -> Blocked
        try:
            verify_tenant_access(customer_user, restaurant_a.id)
            assert False, "Failed: Customer was allowed to access Restaurant A resources"
        except PermissionError as e:
            print(f"✓ Customer access blocked as expected: {e}")

        # 6. Verify verify_restaurant_active
        print("\n2. Testing verify_restaurant_active functions...")
        
        # Active restaurant -> Allowed
        verify_restaurant_active(db, restaurant_a.id)
        print("✓ Active restaurant validation succeeds.")

        # Soft-deleted restaurant -> Blocked
        try:
            verify_restaurant_active(db, restaurant_deleted.id)
            assert False, "Failed: Soft-deleted restaurant passed active check"
        except ValueError as e:
            print(f"✓ Soft-deleted restaurant validation failed as expected: {e}")

        # Inactive restaurant -> Blocked
        try:
            verify_restaurant_active(db, restaurant_inactive.id)
            assert False, "Failed: Inactive restaurant passed active check"
        except ValueError as e:
            print(f"✓ Inactive restaurant validation failed as expected: {e}")

        # 7. Verify AuthService.validate_tenant_access
        print("\n3. Testing AuthService.validate_tenant_access wrapper...")
        
        # Restaurant A token accessing Restaurant A -> OK
        AuthService.validate_tenant_access(db, rest_a_token, restaurant_a.id)
        print("✓ Token-based authentication + tenant access validation succeeds for matching tenant.")

        # Restaurant A token accessing Restaurant B -> Blocked
        try:
            AuthService.validate_tenant_access(db, rest_a_token, restaurant_b.id)
            assert False, "Failed: Token validation allowed cross-tenant access"
        except PermissionError as e:
            print(f"✓ Token validation rejected cross-tenant access as expected: {e}")

        # Admin token accessing soft-deleted restaurant -> Blocked by active check (ValueError)
        try:
            AuthService.validate_tenant_access(db, admin_token, restaurant_deleted.id)
            assert False, "Failed: Admin token validation allowed access to soft-deleted restaurant"
        except ValueError as e:
            print(f"✓ Token validation rejected soft-deleted restaurant access for admin as expected: {e}")

        # Restaurant A token accessing own restaurant after it is soft-deleted -> Blocked by active check (ValueError)
        RestaurantRepository.soft_delete(db, restaurant_a.id)
        try:
            AuthService.validate_tenant_access(db, rest_a_token, restaurant_a.id)
            assert False, "Failed: Restaurant token validation allowed access to soft-deleted own restaurant"
        except ValueError as e:
            print(f"✓ Token validation rejected soft-deleted own restaurant access as expected: {e}")

        # 8. Verify Frontend Session State & Context Locking
        print("\n4. Testing frontend session state initialization and context locking...")
        
        # Admin landing initialization
        st.session_state.clear()
        st.session_state.user = {
            "id": admin_user.id,
            "email": admin_user.email,
            "role": admin_user.role.value,
            "restaurant_id": None
        }
        init_landing_view("admin")
        assert st.session_state.selected_restaurant == "Restaurant_A", f"Failed: Got {st.session_state.selected_restaurant}"
        print("✓ Admin landing initializes selected_restaurant correctly.")

        # Restaurant landing initialization
        st.session_state.clear()
        st.session_state.user = {
            "id": rest_a_user.id,
            "email": rest_a_user.email,
            "role": rest_a_user.role.value,
            "restaurant_id": restaurant_a.id
        }
        init_landing_view("restaurant")
        assert st.session_state.selected_restaurant == restaurant_a.id, f"Failed: Got {st.session_state.selected_restaurant}"
        print("✓ Restaurant landing initializes selected_restaurant to assigned restaurant_id correctly.")

        # Customer landing initialization
        st.session_state.clear()
        st.session_state.user = {
            "id": customer_user.id,
            "email": customer_user.email,
            "role": customer_user.role.value,
            "restaurant_id": None
        }
        init_landing_view("customer")
        assert st.session_state.selected_restaurant == "Restaurant_A", f"Failed: Got {st.session_state.selected_restaurant}"
        print("✓ Customer landing initializes selected_restaurant correctly.")

        # Context Locking via check_auth()
        print("\n5. Testing frontend context locking...")
        st.session_state.clear()
        st.session_state.is_authenticated = True
        st.session_state.access_token = rest_a_token
        st.session_state.user = {
            "id": rest_a_user.id,
            "email": rest_a_user.email,
            "role": rest_a_user.role.value,
            "restaurant_id": restaurant_a.id
        }
        # Simulate dropdown manipulation/tampering
        st.session_state.selected_restaurant = "tampered_restaurant_id"
        
        # Run check_auth which should lock the context
        auth_ok = check_auth()
        assert auth_ok is True
        assert st.session_state.selected_restaurant == restaurant_a.id, f"Failed: Lock failed, got {st.session_state.selected_restaurant}"
        print("✓ Restaurant context locking verified: tampered session state reset to user's database restaurant_id.")

    finally:
        db.close()
        # Clean up database file
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL TENANT ISOLATION FOUNDATION VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_tenant_isolation_tests()
