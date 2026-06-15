import os
import sys

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_rbac_saas.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

from backend.database.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.core.permissions import get_permissions, has_permission, has_role
from backend.services.auth_service import AuthService
from backend.repositories.user_repository import UserRepository

def run_rbac_tests():
    print("=" * 80)
    print("RUNNING ROLE-BASED ACCESS CONTROL (RBAC) VERIFICATION")
    print("=" * 80)

    # 1. Initialize tables
    print("Initializing test database...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Create users for all three roles
        print("\nCreating test users for all roles...")
        customer_user = UserRepository.create(db, "customer@saas.com", "pass1234", UserRole.CUSTOMER)
        restaurant_user = UserRepository.create(db, "restaurant@saas.com", "pass1234", UserRole.RESTAURANT)
        admin_user = UserRepository.create(db, "admin@saas.com", "pass1234", UserRole.ADMIN)

        # Generate tokens
        customer_token = AuthService.create_access_token(customer_user.id, customer_user.email, customer_user.role.value)
        restaurant_token = AuthService.create_access_token(restaurant_user.id, restaurant_user.email, restaurant_user.role.value)
        admin_token = AuthService.create_access_token(admin_user.id, admin_user.email, admin_user.role.value)

        # 2. Verify Customer Permissions
        print("\n1. Verifying Customer permissions mapping...")
        cust_perms = get_permissions(UserRole.CUSTOMER)
        assert "chat:read_write" in cust_perms
        assert "restaurant:view_menu" in cust_perms
        assert "analytics:read_own" not in cust_perms
        assert "admin:manage_system" not in cust_perms
        print("✓ Customer permissions verified successfully.")

        # 3. Verify Restaurant Permissions
        print("\n2. Verifying Restaurant permissions mapping...")
        rest_perms = get_permissions(UserRole.RESTAURANT)
        assert "chat:read_write" in rest_perms
        assert "restaurant:view_menu" in rest_perms
        assert "restaurant:write_profile" in rest_perms
        assert "analytics:read_own" in rest_perms
        assert "analytics:read_all" not in rest_perms
        assert "admin:manage_system" not in rest_perms
        print("✓ Restaurant permissions verified successfully.")

        # 4. Verify Admin Permissions
        print("\n3. Verifying Admin permissions mapping...")
        admin_perms = get_permissions(UserRole.ADMIN)
        assert "chat:read_write" in admin_perms
        assert "restaurant:view_menu" in admin_perms
        assert "analytics:read_own" in admin_perms
        assert "analytics:read_all" in admin_perms
        assert "admin:manage_system" in admin_perms
        print("✓ Admin permissions verified successfully.")

        # 5. Verify Permission Checks Function
        print("\n4. Verifying has_permission checking functions...")
        assert has_permission(UserRole.CUSTOMER, "chat:read_write") is True
        assert has_permission(UserRole.CUSTOMER, "analytics:read_own") is False
        assert has_permission(UserRole.RESTAURANT, "analytics:read_own") is True
        assert has_permission(UserRole.RESTAURANT, "admin:manage_system") is False
        assert has_permission(UserRole.ADMIN, "admin:manage_system") is True
        print("✓ has_permission checks logic verified.")

        # 6. Verify Role Checks Function
        print("\n5. Verifying has_role checking functions...")
        assert has_role(UserRole.CUSTOMER, UserRole.CUSTOMER) is True
        assert has_role(UserRole.CUSTOMER, UserRole.ADMIN) is False
        assert has_role(UserRole.ADMIN, "admin") is True
        assert has_role("restaurant", UserRole.RESTAURANT) is True
        print("✓ has_role checks logic verified.")

        # 7. Verify Backend Authorization Rejection & Acceptance
        print("\n6. Verifying Backend Token-Based Authorization & Rejection...")
        
        # Test valid accesses
        AuthService.authorize_permission(customer_token, "chat:read_write")
        AuthService.authorize_permission(restaurant_token, "analytics:read_own")
        AuthService.authorize_permission(admin_token, "admin:manage_system")
        print("✓ Correct permissions accepted on backend tokens.")

        # Test valid role accesses
        AuthService.authorize_role(customer_token, "customer")
        AuthService.authorize_role(restaurant_token, "restaurant")
        AuthService.authorize_role(admin_token, "admin")
        print("✓ Correct roles accepted on backend tokens.")

        # Test unauthorized permission accesses (Should throw PermissionError)
        try:
            AuthService.authorize_permission(customer_token, "analytics:read_own")
            assert False, "Failed: Customer was allowed analytics access"
        except PermissionError as e:
            assert str(e) == "Permission Denied"
            print("✓ Customer blocked from accessing analytics successfully.")

        try:
            AuthService.authorize_permission(restaurant_token, "admin:manage_system")
            assert False, "Failed: Restaurant was allowed admin control access"
        except PermissionError as e:
            assert str(e) == "Permission Denied"
            print("✓ Restaurant blocked from accessing admin control successfully.")

        # Test unauthorized role accesses (Should throw PermissionError)
        try:
            AuthService.authorize_role(customer_token, "admin")
            assert False, "Failed: Customer was allowed to bypass admin role check"
        except PermissionError as e:
            assert str(e) == "Permission Denied"
            print("✓ Customer blocked from admin role checks successfully.")

        try:
            AuthService.authorize_role(restaurant_token, "customer")
            assert False, "Failed: Restaurant was allowed to bypass customer role check"
        except PermissionError as e:
            assert str(e) == "Permission Denied"
            print("✓ Restaurant blocked from customer role checks successfully.")

    finally:
        db.close()
        # Clean up database file
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL ROLE-BASED ACCESS CONTROL (RBAC) TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_rbac_tests()
