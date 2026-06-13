from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from backend.models.user import User, UserRole
from backend.core.security import hash_password

class UserRepository:
    @staticmethod
    def get_by_id(db: Session, user_id: str) -> Optional[User]:
        """
        Retrieves an active (non-soft-deleted) User by ID.
        """
        return db.query(User).filter(
            User.id == user_id, 
            User.deleted_at.is_(None)
        ).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        """
        Retrieves an active (non-soft-deleted) User by email.
        """
        return db.query(User).filter(
            User.email == email, 
            User.deleted_at.is_(None)
        ).first()

    @staticmethod
    def create(
        db: Session, 
        email: str, 
        password_raw: str, 
        role: UserRole = UserRole.CUSTOMER,
        first_name: Optional[str] = None, 
        last_name: Optional[str] = None
    ) -> User:
        """
        Creates a new User, hashing the raw password before persistence.
        """
        hashed = hash_password(password_raw)
        db_user = User(
            email=email.strip().lower(),
            hashed_password=hashed,
            role=role,
            first_name=first_name,
            last_name=last_name
        )
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        return db_user

    @staticmethod
    def update(db: Session, user_id: str, update_dict: Dict[str, Any]) -> Optional[User]:
        """
        Updates fields of an active User. Hashes plain 'password' key if present.
        """
        user = UserRepository.get_by_id(db, user_id)
        if not user:
            return None
        
        # Hash new password if supplied
        if "password" in update_dict:
            user.hashed_password = hash_password(update_dict.pop("password"))
            
        for key, value in update_dict.items():
            if hasattr(user, key):
                setattr(user, key, value)
                
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def soft_delete(db: Session, user_id: str) -> bool:
        """
        Performs a soft delete by setting the deleted_at timestamp.
        """
        user = UserRepository.get_by_id(db, user_id)
        if not user:
            return False
        user.deleted_at = func.now()
        db.commit()
        return True
