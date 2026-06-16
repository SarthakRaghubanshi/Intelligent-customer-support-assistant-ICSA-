from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from backend.models.restaurant import Restaurant

class RestaurantRepository:
    @staticmethod
    def get_by_id(db: Session, restaurant_id: str) -> Optional[Restaurant]:
        """
        Retrieves an active (non-soft-deleted) Restaurant by ID.
        """
        return db.query(Restaurant).filter(
            Restaurant.id == restaurant_id,
            Restaurant.deleted_at.is_(None)
        ).first()

    @staticmethod
    def get_by_name(db: Session, name: str) -> Optional[Restaurant]:
        """
        Retrieves an active (non-soft-deleted) Restaurant by name (case-insensitive).
        """
        return db.query(Restaurant).filter(
            func.lower(Restaurant.name) == name.strip().lower(),
            Restaurant.deleted_at.is_(None)
        ).first()

    @staticmethod
    def create(
        db: Session,
        name: str,
        phone: Optional[str] = None,
        address: Optional[str] = None,
        description: Optional[str] = None
    ) -> Restaurant:
        """
        Creates and persists a new Restaurant record.
        """
        restaurant = Restaurant(
            name=name.strip(),
            phone=phone.strip() if phone else None,
            address=address.strip() if address else None,
            description=description.strip() if description else None
        )
        db.add(restaurant)
        db.commit()
        db.refresh(restaurant)
        return restaurant

    @staticmethod
    def update(db: Session, restaurant_id: str, update_dict: Dict[str, Any]) -> Optional[Restaurant]:
        """
        Updates the fields of an active Restaurant.
        """
        restaurant = RestaurantRepository.get_by_id(db, restaurant_id)
        if not restaurant:
            return None
            
        for key, value in update_dict.items():
            if hasattr(restaurant, key):
                setattr(restaurant, key, value)
                
        db.commit()
        db.refresh(restaurant)
        return restaurant

    @staticmethod
    def soft_delete(db: Session, restaurant_id: str) -> bool:
        """
        Flags a restaurant as soft-deleted by setting the deleted_at timestamp.
        """
        restaurant = RestaurantRepository.get_by_id(db, restaurant_id)
        if not restaurant:
            return False
        restaurant.deleted_at = func.now()
        db.commit()
        return True

    @staticmethod
    def list_active(db: Session) -> List[Restaurant]:
        """
        Lists all active, non-soft-deleted restaurants.
        """
        return db.query(Restaurant).filter(
            Restaurant.deleted_at.is_(None)
        ).all()

    @staticmethod
    def get_profile(db: Session, restaurant_id: str) -> Optional[Restaurant]:
        """
        Retrieves the profile of an active, non-soft-deleted restaurant.
        """
        return RestaurantRepository.get_by_id(db, restaurant_id)

    @staticmethod
    def update_profile(db: Session, restaurant_id: str, profile_dict: Dict[str, Any]) -> Optional[Restaurant]:
        """
        Updates the profile of an active, non-soft-deleted restaurant.
        """
        return RestaurantRepository.update(db, restaurant_id, profile_dict)
