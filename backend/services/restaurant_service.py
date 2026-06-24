from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.services.auth_service import AuthService
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.models.restaurant import Restaurant

class RestaurantService:
    @staticmethod
    def list_active_restaurants(db: Session):
        """
        Lists all active, non-soft-deleted restaurants.
        """
        return RestaurantRepository.list_active(db)

    @staticmethod
    def onboard_restaurant(
        db: Session,
        email: str,
        password_raw: str,
        first_name: Optional[str],
        last_name: Optional[str],
        restaurant_name: Optional[str] = None,
        existing_restaurant_id: Optional[str] = None
    ):
        """
        Atomically onboards a new restaurant context and creates a manager linked to it.
        """
        if not existing_restaurant_id and not restaurant_name:
            raise ValueError("Either restaurant_name or existing_restaurant_id must be provided for manager onboarding.")
            
        restaurant_id = None
        created_restaurant = None

        try:
            if existing_restaurant_id:
                # Existing restaurant onboarding path
                restaurant = RestaurantRepository.get_by_id(db, existing_restaurant_id)
                if not restaurant:
                    raise ValueError("Target restaurant does not exist or is inactive.")
                restaurant_id = restaurant.id
            else:
                # New restaurant onboarding path
                # Verify unique name constraint beforehand
                existing = RestaurantRepository.get_by_name(db, restaurant_name)
                if existing:
                    raise ValueError(f"Restaurant name '{restaurant_name.strip()}' is already taken.")
                
                created_restaurant = RestaurantRepository.create(
                    db=db,
                    name=restaurant_name
                )
                restaurant_id = created_restaurant.id

            # Create manager user
            from backend.repositories.user_repository import UserRepository
            from backend.models.user import UserRole

            # Validate duplicate user email beforehand
            existing_user = UserRepository.get_by_email(db, email)
            if existing_user:
                raise ValueError("Email already registered")

            user = UserRepository.create(
                db=db,
                email=email,
                password_raw=password_raw,
                role=UserRole.RESTAURANT,
                first_name=first_name,
                last_name=last_name,
                restaurant_id=restaurant_id
            )
            return created_restaurant, user
            
        except Exception as err:
            # Atomic rollback: rollback first to reset session state, then delete the newly created restaurant if manager creation failed
            db.rollback()
            if created_restaurant:
                try:
                    db.delete(created_restaurant)
                    db.commit()
                except Exception:
                    pass
            raise err

    @staticmethod
    def get_profile(db: Session, token: str, restaurant_id: str) -> Restaurant:
        """
        Retrieves the profile of an active restaurant. Enforces explicit role access.
        """
        # Centralized role and tenant validation, verifying active restaurant status
        AuthService.validate_tenant_access(db, token, restaurant_id)
        
        profile = RestaurantRepository.get_profile(db, restaurant_id)
        if not profile:
            raise ValueError("Restaurant is inactive or deleted")
        return profile

    @staticmethod
    def update_profile(db: Session, token: str, restaurant_id: str, update_dict: Dict[str, Any]) -> Restaurant:
        """
        Updates the profile of an active restaurant. Enforces explicit role access and schema validation.
        """
        # Centralized role and tenant validation, verifying active restaurant status
        AuthService.validate_tenant_access(db, token, restaurant_id)
        
        # Validate data via schema
        from backend.schemas.restaurant_schema import RestaurantProfileUpdate
        try:
            validated_data = RestaurantProfileUpdate(**update_dict)
        except Exception as e:
            # Re-raise standard value errors for user friendliness
            raise ValueError(f"Validation Error: {str(e)}")
            
        cleaned_dict = validated_data.model_dump(exclude_unset=True)
        
        updated_profile = RestaurantRepository.update_profile(db, restaurant_id, cleaned_dict)
        if not updated_profile:
            raise ValueError("Restaurant is inactive or deleted")
        return updated_profile

