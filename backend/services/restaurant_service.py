from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.services.auth_service import AuthService
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.models.restaurant import Restaurant

class RestaurantService:
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

