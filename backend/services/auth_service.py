import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from backend.core.config import Config
from backend.models.user import User, UserRole
from backend.repositories.user_repository import UserRepository
from backend.core.security import verify_password
from backend.schemas.token_schema import TokenData

class AuthService:
    @staticmethod
    def register_user(
        db: Session, 
        email: str, 
        password_raw: str, 
        role: UserRole = UserRole.CUSTOMER,
        first_name: Optional[str] = None, 
        last_name: Optional[str] = None
    ) -> User:
        """
        Registers a new user after verifying that the email is not already taken.
        """
        if role == UserRole.RESTAURANT:
            raise ValueError("Restaurant Manager registration must use onboarding endpoint with restaurant context.")
            
        existing_user = UserRepository.get_by_email(db, email)
        if existing_user:
            raise ValueError("Email already registered")
            
        return UserRepository.create(
            db=db,
            email=email,
            password_raw=password_raw,
            role=role,
            first_name=first_name,
            last_name=last_name
        )

    @staticmethod
    def authenticate_user(db: Session, email: str, password_raw: str) -> User:
        """
        Verifies credentials, checks if user is active, and returns the User object.
        """
        user = UserRepository.get_by_email(db, email)
        if not user:
            raise ValueError("Invalid email or password")
            
        if not verify_password(password_raw, user.hashed_password):
            raise ValueError("Invalid email or password")
            
        if not user.is_active:
            raise ValueError("User account is disabled")
            
        return user

    @staticmethod
    def create_access_token(user_id: str, email: str, role: str) -> str:
        """
        Generates a stateless JWT access token signed with Config.JWT_SECRET_KEY.
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=Config.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        payload = {
            "sub": user_id,
            "email": email,
            "role": role,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp())
        }
        
        token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)
        return token

    @staticmethod
    def validate_access_token(token: str) -> TokenData:
        """
        Decodes and verifies a JWT token. Raises ValueError on expiration or invalid signature.
        """
        try:
            payload = jwt.decode(
                token, 
                Config.JWT_SECRET_KEY, 
                algorithms=[Config.JWT_ALGORITHM]
            )
            
            user_id = payload.get("sub")
            email = payload.get("email")
            role = payload.get("role")
            
            if not user_id or not email or not role:
                raise ValueError("Invalid token payload")
                
            return TokenData(user_id=user_id, email=email, role=role)
            
        except jwt.ExpiredSignatureError:
            raise ValueError("Token signature has expired")
        except jwt.InvalidTokenError:
            raise ValueError("Invalid authentication token")

    @staticmethod
    def get_current_user(db: Session, token: str) -> User:
        """
        Validates the token and retrieves the corresponding active User from the database.
        """
        token_data = AuthService.validate_access_token(token)
        user = UserRepository.get_by_id(db, token_data.user_id)
        if not user:
            raise ValueError("User not found")
        if not user.is_active:
            raise ValueError("User account is disabled")
        return user

    @staticmethod
    def authorize_permission(token: str, required_permission: str) -> TokenData:
        """
        Validates the token and verifies the user has the required permission.
        Raises PermissionError if unauthorized.
        """
        from backend.core.permissions import has_permission
        token_data = AuthService.validate_access_token(token)
        if not has_permission(token_data.role, required_permission):
            raise PermissionError("Permission Denied")
        return token_data

    @staticmethod
    def authorize_role(token: str, required_role: str) -> TokenData:
        """
        Validates the token and verifies the user has the required role.
        Raises PermissionError if unauthorized.
        """
        from backend.core.permissions import has_role
        token_data = AuthService.validate_access_token(token)
        if not has_role(token_data.role, required_role):
            raise PermissionError("Permission Denied")
        return token_data

    @staticmethod
    def validate_tenant_access(db: Session, token: str, target_restaurant_id: str) -> User:
        """
        Retrieves current user, verifies their tenant access rights, 
        and ensures the target restaurant is active.
        """
        from backend.core.tenant import verify_tenant_access, verify_restaurant_active
        user = AuthService.get_current_user(db, token)
        verify_tenant_access(user, target_restaurant_id)
        verify_restaurant_active(db, target_restaurant_id)
        return user


