import os
import sys

# Ensure project root is in the path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.database.database import SessionLocal
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.user_repository import UserRepository
from backend.models.user import UserRole
from backend.services.restaurant_service import RestaurantService

def seed():
    db = SessionLocal()
    try:
        # Check if restaurant exists
        rest = RestaurantRepository.get_by_name(db, "La Piazza")
        if not rest:
            rest = RestaurantRepository.create(db, "La Piazza")
            print(f"Created restaurant: {rest.name} ({rest.id})")
        else:
            print(f"Restaurant already exists: {rest.name}")

        # Check and create admin@saas.com
        admin = UserRepository.get_by_email(db, "admin@saas.com")
        if not admin:
            admin = UserRepository.create(
                db=db,
                email="admin@saas.com",
                password_raw="password123",
                role=UserRole.ADMIN,
                first_name="Super",
                last_name="Admin"
            )
            print(f"Created admin user: {admin.email}")
        else:
            print(f"Admin user already exists: {admin.email}")

        # Check and create customer@saas.com
        customer = UserRepository.get_by_email(db, "customer@saas.com")
        if not customer:
            customer = UserRepository.create(
                db=db,
                email="customer@saas.com",
                password_raw="password123",
                role=UserRole.CUSTOMER,
                first_name="John",
                last_name="Doe"
            )
            print(f"Created customer user: {customer.email}")
        else:
            print(f"Customer user already exists: {customer.email}")

        # Check and create manager1@saas.com
        manager1 = UserRepository.get_by_email(db, "manager1@saas.com")
        if not manager1:
            manager1 = UserRepository.create(
                db=db,
                email="manager1@saas.com",
                password_raw="password123",
                role=UserRole.RESTAURANT,
                first_name="Marco",
                last_name="Rossi",
                restaurant_id=rest.id
            )
            print(f"Created manager1 user: {manager1.email}")
        else:
            print(f"Manager1 user already exists: {manager1.email}")

        db.commit()
    finally:
        db.close()

if __name__ == "__main__":
    seed()
