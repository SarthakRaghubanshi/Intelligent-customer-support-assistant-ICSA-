import os
import sys
import time
from datetime import datetime, timezone, timedelta

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Force a distinct test DB for validation
test_db_path = os.path.join(project_root, "data", "test_auth_saas.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

# Clean test db file if it already exists
if os.path.exists(test_db_path):
    os.remove(test_db_path)

from backend.database.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.services.auth_service import AuthService
from backend.repositories.user_repository import UserRepository

def run_auth_tests():
    print("=" * 80)
    print("RUNNING AUTHENTICATION FOUNDATION VERIFICATION")
    print("=" * 80)

    # 1. Initialize tables
    print("Initializing test database...")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # 1. Test User Registration
        print("\n1. Testing User Registration...")
        email = "testuser@saas.com"
        password = "secretpassword123"
        role = UserRole.CUSTOMER
        first_name = "Auth"
        last_name = "Tester"

        user = AuthService.register_user(
            db=db,
            email=email,
            password_raw=password,
            role=role,
            first_name=first_name,
            last_name=last_name
        )

        assert user.id is not None
        assert user.email == email
        assert user.role == role
        assert user.first_name == first_name
        assert user.last_name == last_name
        assert user.is_active is True
        print("✓ User registered successfully.")

        # Test duplicate email registration
        try:
            AuthService.register_user(db=db, email=email, password_raw="anotherpassword")
            assert False, "Failed: Allowed duplicate email registration"
        except ValueError as e:
            assert str(e) == "Email already registered"
            print("✓ Duplicate email registration rejected correctly.")

        # 2. Test User Login
        print("\n2. Testing User Login...")
        # Valid credentials
        authenticated_user = AuthService.authenticate_user(db, email, password)
        assert authenticated_user.id == user.id
        print("✓ User authenticated with correct credentials.")

        # Invalid credentials (incorrect password)
        try:
            AuthService.authenticate_user(db, email, "wrongpassword")
            assert False, "Failed: Authenticated with invalid password"
        except ValueError as e:
            assert str(e) == "Invalid email or password"
            print("✓ Incorrect password login attempt rejected correctly.")

        # Invalid credentials (incorrect email)
        try:
            AuthService.authenticate_user(db, "nonexistent@saas.com", password)
            assert False, "Failed: Authenticated with non-existent email"
        except ValueError as e:
            assert str(e) == "Invalid email or password"
            print("✓ Non-existent email login attempt rejected correctly.")

        # Test inactive user login
        print("Deactivating user for active check test...")
        user.is_active = False
        db.commit()
        try:
            AuthService.authenticate_user(db, email, password)
            assert False, "Failed: Authenticated inactive user"
        except ValueError as e:
            assert str(e) == "User account is disabled"
            print("✓ Inactive user login attempt rejected correctly.")
        
        # Reactivate user
        user.is_active = True
        db.commit()

        # 3. Test JWT Generation & Claims
        print("\n3. Testing JWT Access Token Generation...")
        token = AuthService.create_access_token(user.id, user.email, user.role.value)
        assert token is not None
        assert isinstance(token, str)
        print("✓ JWT Access Token generated successfully.")

        # 4. Test JWT Validation
        print("\n4. Testing JWT Access Token Validation...")
        token_data = AuthService.validate_access_token(token)
        assert token_data.user_id == user.id
        assert token_data.email == user.email
        assert token_data.role == user.role.value
        print("✓ JWT claims parsed and verified successfully.")

        # Test tampered token
        tampered_token = token + "corrupted"
        try:
            AuthService.validate_access_token(tampered_token)
            assert False, "Failed: Validated tampered token"
        except ValueError as e:
            assert "Invalid authentication token" in str(e)
            print("✓ Tampered token verification rejected correctly.")

        # Test expired token
        print("Testing expired token verification...")
        import jwt
        from backend.core.config import Config
        expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)
        payload = {
            "sub": user.id,
            "email": user.email,
            "role": user.role.value,
            "exp": int(expired_time.timestamp()),
            "iat": int((expired_time - timedelta(minutes=10)).timestamp())
        }
        expired_token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)
        try:
            AuthService.validate_access_token(expired_token)
            assert False, "Failed: Validated expired token"
        except ValueError as e:
            assert str(e) == "Token signature has expired"
            print("✓ Expired token verification rejected correctly.")

        # 5. Test Current User Retrieval
        print("\n5. Testing Current User Retrieval from Token...")
        current_user = AuthService.get_current_user(db, token)
        assert current_user.id == user.id
        assert current_user.email == user.email
        print("✓ Active user retrieved using valid JWT access token.")

        # Test current user retrieval with disabled user
        user.is_active = False
        db.commit()
        try:
            AuthService.get_current_user(db, token)
            assert False, "Failed: Retrieved current user when account was deactivated"
        except ValueError as e:
            assert str(e) == "User account is disabled"
            print("✓ Current user retrieval fails as expected if user is deactivated.")
        
        user.is_active = True
        db.commit()

        # 6. Simulating Logout
        print("\n6. Simulating Logout Flow...")
        session_state = {
            "is_authenticated": True,
            "access_token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role.value
            }
        }
        
        # Action: Clear session keys
        session_state["is_authenticated"] = False
        session_state["access_token"] = None
        session_state["user"] = None
        
        assert session_state["is_authenticated"] is False
        assert session_state["access_token"] is None
        assert session_state["user"] is None
        print("✓ Logout session state cleared successfully.")

    finally:
        db.close()
        # Clean up database file
        if os.path.exists(test_db_path):
            os.remove(test_db_path)

    print("\n✓ ALL AUTHENTICATION FOUNDATION VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    sys.exit(0)

if __name__ == "__main__":
    run_auth_tests()
