from sqlalchemy.orm import Session
from backend.models.user import User, UserRole
from backend.repositories.restaurant_repository import RestaurantRepository

def verify_tenant_access(user: User, target_restaurant_id: str) -> None:
    """
    Verifies that a user has permission to access a specific restaurant tenant.
    - Admin: Full override access allowed.
    - Restaurant: Access allowed only to their linked restaurant_id.
    - Customer: Blocked from accessing restaurant backend resources.
    """
    if user.role == UserRole.ADMIN:
        return  # Admin override permitted
        
    if user.role == UserRole.RESTAURANT:
        if not user.restaurant_id or user.restaurant_id != target_restaurant_id:
            raise PermissionError("Permission Denied: Tenant isolation constraint violated")
        return
        
    # Customer or any other unauthorized role
    raise PermissionError("Permission Denied: Customers cannot access restaurant resources")

def verify_restaurant_active(db: Session, restaurant_id: str) -> None:
    """
    Verifies that a restaurant exists, is active, and is not soft-deleted.
    Raises ValueError if validation fails.
    """
    restaurant = RestaurantRepository.get_by_id(db, restaurant_id)
    if not restaurant or not restaurant.is_active:
        raise ValueError("Restaurant is inactive or deleted")
