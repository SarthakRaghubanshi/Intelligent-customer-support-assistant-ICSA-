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
    def public_onboard_restaurant(
        db: Session,
        email: str,
        password_raw: str,
        first_name: Optional[str],
        last_name: Optional[str],
        restaurant_name: str
    ):
        """
        Atomically creates a new restaurant and the owner manager associated with it.
        Publicly accessible flow without authentication/token checks.
        """
        if not restaurant_name or not restaurant_name.strip():
            raise ValueError("Restaurant name is required for manager onboarding.")

        # Check duplicate restaurant name constraint
        existing = RestaurantRepository.get_by_name(db, restaurant_name)
        if existing:
            raise ValueError(f"Restaurant name '{restaurant_name.strip()}' is already taken.")

        # Validate duplicate user email beforehand
        from backend.repositories.user_repository import UserRepository
        existing_user = UserRepository.get_by_email(db, email)
        if existing_user:
            raise ValueError("Email already registered")

        created_restaurant = None
        try:
            # Create new restaurant
            created_restaurant = RestaurantRepository.create(
                db=db,
                name=restaurant_name
            )
            restaurant_id = created_restaurant.id

            # Create owner manager user
            from backend.models.user import UserRole
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
            db.rollback()
            if created_restaurant:
                try:
                    db.delete(created_restaurant)
                    db.commit()
                except Exception:
                    pass
            raise err

    @staticmethod
    def invite_manager(
        db: Session,
        token: str,
        email: str,
        password_raw: str,
        first_name: Optional[str],
        last_name: Optional[str],
        existing_restaurant_id: str
    ):
        """
        Invites/onboards a new manager user into an existing restaurant context.
        Requires owner/admin authorization via token verification.
        """
        if not existing_restaurant_id:
            raise ValueError("existing_restaurant_id is required.")

        # Require owner/admin authorization
        AuthService.validate_tenant_access(db, token, existing_restaurant_id)

        # Check existing restaurant
        restaurant = RestaurantRepository.get_by_id(db, existing_restaurant_id)
        if not restaurant:
            raise ValueError("Target restaurant does not exist or is inactive.")

        # Check duplicate manager email
        from backend.repositories.user_repository import UserRepository
        existing_user = UserRepository.get_by_email(db, email)
        if existing_user:
            raise ValueError("Email already registered")

        # Create manager user
        from backend.models.user import UserRole
        user = UserRepository.create(
            db=db,
            email=email,
            password_raw=password_raw,
            role=UserRole.RESTAURANT,
            first_name=first_name,
            last_name=last_name,
            restaurant_id=existing_restaurant_id
        )
        return restaurant, user

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

    # ------------------------------------------------------------------
    # AI assistant configuration (PRD Section 11)
    # ------------------------------------------------------------------
    # Each escalation rule can be toggled per restaurant (PRD Section 11 —
    # "configure escalation rules").
    DEFAULT_ENABLED_RULES = {
        "refund": True, "complaint": True, "abuse": True,
        "human": True, "negative": True, "low_confidence": True,
    }
    DEFAULT_AI_CONFIG = {
        "ai_enabled": True,
        "greeting": "",  # filled per-restaurant in get_ai_config if unset
        "low_confidence_threshold": 0.6,
        "enabled_rules": DEFAULT_ENABLED_RULES,
    }

    @staticmethod
    def get_ai_config(db: Session, restaurant_id: str) -> Dict[str, Any]:
        """Return the restaurant's AI settings merged over sensible defaults.
        No token required — used by the chat pipeline itself."""
        restaurant = RestaurantRepository.get_by_id(db, restaurant_id)
        cfg = dict(RestaurantService.DEFAULT_AI_CONFIG)
        if restaurant and restaurant.ai_config:
            cfg.update(restaurant.ai_config)
        if not cfg.get("greeting"):
            name = restaurant.name if restaurant else "our"
            cfg["greeting"] = f"Hi! I'm the {name} assistant. How can I help you today?"
        # Deep-merge escalation-rule toggles over the defaults so partial configs work.
        merged_rules = dict(RestaurantService.DEFAULT_ENABLED_RULES)
        if isinstance(cfg.get("enabled_rules"), dict):
            merged_rules.update(cfg["enabled_rules"])
        cfg["enabled_rules"] = merged_rules
        return cfg

    @staticmethod
    def update_ai_config(db: Session, token: str, restaurant_id: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Update the restaurant's AI settings (owner/admin only)."""
        AuthService.validate_tenant_access(db, token, restaurant_id)
        current = RestaurantService.get_ai_config(db, restaurant_id)
        for key in ("ai_enabled", "greeting", "low_confidence_threshold", "enabled_rules"):
            if key in config and config[key] is not None:
                current[key] = config[key]
        RestaurantRepository.update(db, restaurant_id, {"ai_config": current})
        try:
            from backend.services.audit_service import AuditService
            AuditService.log(db, action="aiconfig.update", entity_type="restaurant",
                             entity_id=restaurant_id, restaurant_id=restaurant_id,
                             detail="AI assistant settings updated")
        except Exception:
            pass
        return current

