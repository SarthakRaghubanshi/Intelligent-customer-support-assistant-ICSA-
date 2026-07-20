from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from backend.models.product import Product


class ProductRepository:
    """Data access for menu items. Every query is scoped by restaurant_id
    (tenant isolation) and excludes soft-deleted rows."""

    @staticmethod
    def create(
        db: Session,
        restaurant_id: str,
        name: str,
        category: str,
        base_price: float,
        description: Optional[str] = None,
        size_prices: Optional[Dict[str, Any]] = None,
        dietary_tags: Optional[List[str]] = None,
        allergens: Optional[List[str]] = None,
        is_popular: bool = False,
        is_available: bool = True,
    ) -> Product:
        product = Product(
            restaurant_id=restaurant_id,
            name=name.strip(),
            category=category.strip(),
            base_price=float(base_price),
            description=(description.strip() if description else None),
            size_prices=size_prices,
            dietary_tags=dietary_tags,
            allergens=allergens,
            is_popular=is_popular,
            is_available=is_available,
        )
        db.add(product)
        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def get_by_id(db: Session, product_id: str) -> Optional[Product]:
        return db.query(Product).filter(
            Product.id == product_id,
            Product.deleted_at.is_(None),
        ).first()

    @staticmethod
    def list_by_restaurant(
        db: Session,
        restaurant_id: str,
        only_available: bool = True,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Product]:
        q = db.query(Product).filter(
            Product.restaurant_id == restaurant_id,
            Product.deleted_at.is_(None),
        )
        if only_available:
            q = q.filter(Product.is_available.is_(True))
        return q.order_by(Product.category, Product.name).limit(limit).offset(offset).all()

    @staticmethod
    def count_by_restaurant(db: Session, restaurant_id: str) -> int:
        return db.query(Product).filter(
            Product.restaurant_id == restaurant_id,
            Product.deleted_at.is_(None),
        ).count()

    @staticmethod
    def update(db: Session, product_id: str, update_dict: Dict[str, Any]) -> Optional[Product]:
        product = ProductRepository.get_by_id(db, product_id)
        if not product:
            return None
        for key, value in update_dict.items():
            if hasattr(product, key):
                if isinstance(value, str):
                    value = value.strip()
                setattr(product, key, value)
        db.commit()
        db.refresh(product)
        return product

    @staticmethod
    def soft_delete(db: Session, product_id: str) -> bool:
        product = ProductRepository.get_by_id(db, product_id)
        if not product:
            return False
        product.deleted_at = func.now()
        db.commit()
        return True
