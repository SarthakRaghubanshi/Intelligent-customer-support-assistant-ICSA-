import uuid
from sqlalchemy import Column, String, Text, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database.database import Base


class Product(Base):
    """
    A single menu item belonging to one restaurant (tenant).

    Powers the Menu Discovery Assistant (PRD Module 4) and Order Modification
    (Module 6). Dietary tags / allergens / price enable structured filtering
    (e.g. "show vegan items under 400"), while the free-text description is also
    indexed into the knowledge base for RAG answers.
    """
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Tenant boundary — every product belongs to exactly one restaurant.
    restaurant_id = Column(String(36), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Human-readable menu section, e.g. "Vegetarian Pizzas", "Ramen", "Beverages".
    category = Column(String(120), nullable=False, index=True)

    # Base price (smallest size / single serving). `size_prices` holds variant
    # pricing when a product comes in multiple sizes, e.g.
    # {"Personal 10\"": 299, "Medium 12\"": 499, "Large 16\"": 799}.
    base_price = Column(Float, nullable=False, default=0.0)
    size_prices = Column(JSON, nullable=True)

    # Structured filtering aids. dietary_tags e.g. ["vegetarian"], ["vegan"],
    # ["non-vegetarian"]; allergens e.g. ["Wheat/Gluten", "Milk"].
    dietary_tags = Column(JSON, nullable=True)
    allergens = Column(JSON, nullable=True)

    is_popular = Column(Boolean, nullable=False, default=False)
    is_available = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    restaurant = relationship("Restaurant", back_populates="products")
    order_items = relationship("OrderItem", back_populates="product")
