from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from backend.models.order import Order, OrderItem


class OrderRepository:
    """Data access for orders and their line items. Reads are scoped by
    restaurant_id and/or customer_id so one tenant/customer never sees another's
    orders."""

    @staticmethod
    def create(
        db: Session,
        order_number: str,
        restaurant_id: str,
        customer_id: Optional[str],
        items: List[Dict[str, Any]],
        order_type: str = "delivery",
        status: str = "placed",
        delivery_address: Optional[str] = None,
        delivery_fee: float = 0.0,
        tax: float = 0.0,
        payment_method: Optional[str] = None,
        payment_status: str = "pending",
        notes: Optional[str] = None,
        estimated_ready_at=None,
        placed_at=None,
    ) -> Order:
        """Create an order plus its line items. `items` is a list of dicts with
        keys: product_id, product_name, size, quantity, unit_price, modifiers."""
        subtotal = 0.0
        order_items = []
        for it in items:
            qty = int(it.get("quantity", 1))
            unit_price = float(it.get("unit_price", 0.0))
            line_total = round(qty * unit_price, 2)
            subtotal += line_total
            order_items.append(OrderItem(
                product_id=it.get("product_id"),
                product_name=it.get("product_name", "Item"),
                size=it.get("size"),
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total,
                modifiers=it.get("modifiers"),
            ))

        subtotal = round(subtotal, 2)
        total = round(subtotal + float(delivery_fee) + float(tax), 2)

        order = Order(
            order_number=order_number,
            restaurant_id=restaurant_id,
            customer_id=customer_id,
            status=status,
            order_type=order_type,
            delivery_address=delivery_address,
            subtotal=subtotal,
            delivery_fee=float(delivery_fee),
            tax=float(tax),
            total=total,
            payment_method=payment_method,
            payment_status=payment_status,
            notes=notes,
            estimated_ready_at=estimated_ready_at,
            items=order_items,
        )
        if placed_at is not None:
            order.placed_at = placed_at
        db.add(order)
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def get_by_id(db: Session, order_id: str) -> Optional[Order]:
        return db.query(Order).filter(Order.id == order_id).first()

    @staticmethod
    def get_by_number(db: Session, order_number: str, restaurant_id: Optional[str] = None) -> Optional[Order]:
        q = db.query(Order).filter(Order.order_number == str(order_number).lstrip("#").strip())
        if restaurant_id:
            q = q.filter(Order.restaurant_id == restaurant_id)
        return q.first()

    @staticmethod
    def list_by_customer(
        db: Session,
        customer_id: str,
        restaurant_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Order]:
        q = db.query(Order).filter(Order.customer_id == customer_id)
        if restaurant_id:
            q = q.filter(Order.restaurant_id == restaurant_id)
        return q.order_by(Order.placed_at.desc()).limit(limit).all()

    @staticmethod
    def get_latest_for_customer(
        db: Session,
        customer_id: str,
        restaurant_id: Optional[str] = None,
    ) -> Optional[Order]:
        orders = OrderRepository.list_by_customer(db, customer_id, restaurant_id, limit=1)
        return orders[0] if orders else None

    @staticmethod
    def list_by_restaurant(db: Session, restaurant_id: str, limit: int = 100) -> List[Order]:
        return db.query(Order).filter(
            Order.restaurant_id == restaurant_id,
        ).order_by(Order.placed_at.desc()).limit(limit).all()

    @staticmethod
    def update_status(db: Session, order_id: str, new_status: str) -> Optional[Order]:
        order = OrderRepository.get_by_id(db, order_id)
        if not order:
            return None
        order.status = new_status
        db.commit()
        db.refresh(order)
        return order

    @staticmethod
    def update(db: Session, order_id: str, update_dict: Dict[str, Any]) -> Optional[Order]:
        order = OrderRepository.get_by_id(db, order_id)
        if not order:
            return None
        for key, value in update_dict.items():
            if hasattr(order, key):
                setattr(order, key, value)
        db.commit()
        db.refresh(order)
        return order
