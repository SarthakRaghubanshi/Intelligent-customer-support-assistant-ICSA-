import uuid
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database.database import Base


# Canonical order lifecycle statuses (PRD Module 3 — Order Status Assistant).
ORDER_STATUSES = [
    "placed",           # created, awaiting restaurant acceptance
    "confirmed",        # restaurant accepted the order
    "preparing",        # kitchen is preparing
    "ready",            # ready for pickup / awaiting driver
    "out_for_delivery", # driver en route
    "delivered",        # completed (delivery)
    "completed",        # completed (pickup)
    "cancelled",        # cancelled
]

ORDER_TYPES = ["delivery", "pickup"]


class Order(Base):
    """
    A customer order for one restaurant (tenant).

    Backs the Order Status Assistant (PRD Module 3), Order Modification
    Assistant (Module 6), and Personalized Recommendations (Module 10, via
    per-customer order history). `order_number` is the short, human-friendly
    reference customers use in chat (e.g. "where is order #1254?").
    """
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Short human-friendly reference shown to customers (unique across platform).
    order_number = Column(String(20), nullable=False, unique=True, index=True)

    # Tenant boundary + owning customer.
    restaurant_id = Column(String(36), ForeignKey("restaurants.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    status = Column(String(50), nullable=False, default="placed", index=True)
    order_type = Column(String(20), nullable=False, default="delivery")

    delivery_address = Column(String(500), nullable=True)

    # Monetary breakdown (currency is INR across seed data).
    subtotal = Column(Float, nullable=False, default=0.0)
    delivery_fee = Column(Float, nullable=False, default=0.0)
    tax = Column(Float, nullable=False, default=0.0)
    total = Column(Float, nullable=False, default=0.0)

    payment_method = Column(String(50), nullable=True)
    payment_status = Column(String(20), nullable=False, default="pending")  # paid / cod / pending

    # Contact phone for the order — updatable via the Order Modification assistant.
    contact_phone = Column(String(50), nullable=True)

    # Free-text special instructions (order-modification target).
    notes = Column(Text, nullable=True)

    # Timing. placed_at drives the modification/cancellation window (e.g. changes
    # only allowed within 5 minutes). estimated_ready_at powers ETA answers.
    placed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    estimated_ready_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)

    restaurant = relationship("Restaurant", back_populates="orders")
    customer = relationship("User", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    """A single line item within an Order (a product + quantity + chosen size)."""
    __tablename__ = "order_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    order_id = Column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)

    # Nullable FK so a product deletion doesn't erase order history; the name is
    # denormalized as a snapshot of what was actually ordered.
    product_id = Column(String(36), ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    product_name = Column(String(255), nullable=False)

    size = Column(String(60), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0.0)
    line_total = Column(Float, nullable=False, default=0.0)

    # Customizations, e.g. {"added": ["Extra Mozzarella"], "removed": ["Olives"]}.
    modifiers = Column(JSON, nullable=True)

    order = relationship("Order", back_populates="items")
    product = relationship("Product", back_populates="order_items")
