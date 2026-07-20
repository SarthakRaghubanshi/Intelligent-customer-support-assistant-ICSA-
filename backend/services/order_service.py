import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from collections import Counter
from sqlalchemy.orm import Session

from backend.repositories.order_repository import OrderRepository
from backend.repositories.product_repository import ProductRepository
from backend.repositories.restaurant_repository import RestaurantRepository

# How long after placement a customer may still change/cancel an order
# (Pizza Paradise business rule: modifications only within 5 minutes).
MODIFY_WINDOW_MINUTES = 5

# Human-friendly status descriptions used in chat answers.
STATUS_TEXT = {
    "placed": "received and waiting for the restaurant to accept it",
    "confirmed": "confirmed and accepted by the restaurant",
    "preparing": "being prepared in the kitchen",
    "ready": "ready for pickup",
    "out_for_delivery": "out for delivery",
    "delivered": "delivered",
    "completed": "completed",
    "cancelled": "cancelled",
}

_ORDER_NUM_RE = re.compile(r"#?\s*(\d{3,})")


def _minutes_since(dt) -> float:
    if dt is None:
        return 1e9
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 60.0


def extract_order_number(text: str) -> Optional[str]:
    """Pull an order number like '#1254' or 'order 1254' out of free text."""
    if not text:
        return None
    m = _ORDER_NUM_RE.search(text)
    return m.group(1) if m else None


def _order_to_dict(order) -> Dict[str, Any]:
    return {
        "id": order.id,
        "order_number": order.order_number,
        "status": order.status,
        "order_type": order.order_type,
        "total": order.total,
        "placed_at": order.placed_at.isoformat() if order.placed_at else None,
        "estimated_ready_at": order.estimated_ready_at.isoformat() if order.estimated_ready_at else None,
        "items": [
            {"name": i.product_name, "size": i.size, "quantity": i.quantity, "line_total": i.line_total}
            for i in order.items
        ],
    }


def _seasonal_prefs() -> list:
    """Season-appropriate category keywords for the current month (recommendations)."""
    month = datetime.now(timezone.utc).month
    if month in (3, 4, 5, 6):        # hot season -> lighter / cold
        return ["beverage", "shake", "dessert", "salad", "side", "starter"]
    if month in (7, 8, 9):           # monsoon -> warm comfort
        return ["ramen", "pasta", "soup", "burger"]
    return ["pizza", "ramen", "burger", "non-vegetarian"]  # cool/winter -> hearty


# --- Order-modification parsing (PRD Module 6) -----------------------------
_PHONE_RE = re.compile(r'(\+?\d[\d\s\-]{7,14}\d)')
_ADD_KEYS = r'(?:add|extra|include|put|more|with)'
_REMOVE_KEYS = r'(?:remove|without|no|hold\s+the|leave\s+out|take\s+off|less)'
_DELIVERY_KEYS = r'(?:leave\s+it|leave\s+at|ring|gate|door|buzz|drop|deliver\s+to|delivery\s+instruction|address)'


def _capture_object(text: str, keys: str):
    """Capture the noun phrase after an action keyword, e.g. 'add extra cheese' -> 'extra cheese'."""
    m = re.search(keys + r'\s+(?:some\s+|a\s+|an\s+|the\s+|my\s+)?([a-z][a-z\s-]{1,25})', text, re.IGNORECASE)
    if not m:
        return None
    obj = m.group(1).strip()
    obj = re.sub(r'\b(and|to|on|for|please|from|my|order|it|instead)\b.*$', '', obj).strip(" -,.")
    return obj or None


def _pick_target_item(order, text: str):
    """Choose which line item a modification refers to. Prefer the item the
    customer named in the instruction; fall back to the only/first item."""
    if not order.items:
        return None
    low = (text or "").lower()
    # Exact product-name mention wins.
    for it in order.items:
        if it.product_name and it.product_name.lower() in low:
            return it
    # Otherwise match on a significant word from the product name.
    for it in order.items:
        words = [w for w in re.findall(r"[a-z]+", (it.product_name or "").lower()) if len(w) > 3]
        if any(w in low for w in words):
            return it
    return order.items[0]


class OrderService:
    """Order Status (Module 3), Order Modification (Module 6), and the
    order-history side of Personalized Recommendations (Module 10).

    Every lookup is scoped to the calling restaurant AND the calling customer,
    so a customer can only ever see their own orders."""

    @staticmethod
    def get_order_status(
        db: Session,
        restaurant_id: str,
        customer_id: Optional[str] = None,
        order_number: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Look up an order and return a grounded, human-readable status summary."""
        order = None
        if order_number:
            order = OrderRepository.get_by_number(db, order_number, restaurant_id=restaurant_id)
            # Enforce ownership: a customer may only view their own order.
            if order and customer_id and order.customer_id and order.customer_id != customer_id:
                order = None
        elif customer_id:
            order = OrderRepository.get_latest_for_customer(db, customer_id, restaurant_id)

        if not order:
            return {
                "found": False,
                "summary": (
                    "I couldn't find that order on your account for this restaurant. "
                    "Please double-check the order number, or make sure you're signed in with the "
                    "account used to place the order."
                ),
            }

        status_desc = STATUS_TEXT.get(order.status, order.status)
        summary = f"Your order #{order.order_number} is currently {status_desc}."
        if order.status in ("preparing", "confirmed", "placed") and order.estimated_ready_at:
            eta_min = int(round(-_minutes_since(order.estimated_ready_at)))
            if eta_min > 0:
                unit = "ready for pickup" if order.order_type == "pickup" else "delivered"
                summary += f" It should be {unit} in about {eta_min} minutes."
        elif order.status == "out_for_delivery" and order.estimated_ready_at:
            eta_min = int(round(-_minutes_since(order.estimated_ready_at)))
            if eta_min > 0:
                summary += f" Estimated arrival in about {eta_min} minutes."

        result = _order_to_dict(order)
        result["found"] = True
        result["summary"] = summary
        return result

    @staticmethod
    def get_customer_orders(db: Session, customer_id: str, restaurant_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return [_order_to_dict(o) for o in OrderRepository.list_by_customer(db, customer_id, restaurant_id)]

    @staticmethod
    def can_modify(order) -> Dict[str, Any]:
        """Determine whether an order may still be changed, per the restaurant's
        modification window and current status."""
        if order.status in ("delivered", "completed", "cancelled"):
            return {"allowed": False, "reason": f"This order is already {order.status} and can no longer be changed."}
        if order.status in ("out_for_delivery", "ready"):
            return {"allowed": False, "reason": "This order has already left the kitchen, so it can no longer be modified."}
        mins = _minutes_since(order.placed_at)
        if mins > MODIFY_WINDOW_MINUTES:
            return {
                "allowed": False,
                "reason": (
                    f"Orders can only be changed within {MODIFY_WINDOW_MINUTES} minutes of being placed. "
                    "Preparation has already started, so this order is locked."
                ),
            }
        return {"allowed": True, "reason": f"Within the {MODIFY_WINDOW_MINUTES}-minute change window."}

    @staticmethod
    def modify_order(
        db: Session,
        restaurant_id: str,
        customer_id: str,
        order_number: str,
        instruction: str,
    ) -> Dict[str, Any]:
        """Parse and APPLY a customer's modification if the rules allow it:
        cancellation, item add/remove (structured modifiers), delivery
        instructions, and contact-number updates. Returns an honest summary of
        exactly what was applied. (Topping re-pricing is left to a real POS.)"""
        order = OrderRepository.get_by_number(db, order_number, restaurant_id=restaurant_id)
        if not order or (order.customer_id and order.customer_id != customer_id):
            return {"success": False, "summary": "I couldn't find that order on your account for this restaurant."}

        check = OrderService.can_modify(order)
        if not check["allowed"]:
            return {"success": False, "summary": check["reason"]}

        instr = instruction.strip()
        low = instr.lower()
        changes = []

        # Cancellation
        if re.search(r'\bcancel\b', low):
            order.status = "cancelled"
            db.commit()
            return {
                "success": True,
                "summary": (
                    f"Your order #{order.order_number} has been cancelled. Any eligible refund "
                    "will be processed to your original payment method."
                ),
            }

        # Contact-number update
        phone = _PHONE_RE.search(instr)
        if phone:
            order.contact_phone = phone.group(1).strip()
            changes.append(f"updated the contact number to {order.contact_phone}")

        # Item / topping add + remove -> structured modifiers on the line item
        # the customer actually named (not blindly the first one).
        added = _capture_object(low, _ADD_KEYS)
        removed = _capture_object(low, _REMOVE_KEYS)
        if (added or removed) and order.items:
            item = _pick_target_item(order, instr)
            mods = dict(item.modifiers or {})
            if added:
                mods["added"] = (mods.get("added") or []) + [added]
                changes.append(f"added \"{added}\" to {item.product_name}")
            if removed:
                mods["removed"] = (mods.get("removed") or []) + [removed]
                changes.append(f"removed \"{removed}\" from {item.product_name}")
            item.modifiers = mods  # reassign so SQLAlchemy flags the JSON change

        # Delivery instructions
        if not phone and re.search(_DELIVERY_KEYS, low):
            existing = (order.notes + " | ") if order.notes else ""
            order.notes = existing + "Delivery note: " + instr
            changes.append("saved your delivery instructions")

        if not changes:
            existing = (order.notes + " | ") if order.notes else ""
            order.notes = existing + "Customer request: " + instr
            changes.append("recorded your request for the kitchen")

        db.commit()
        return {
            "success": True,
            "summary": (
                f"Done — for order #{order.order_number} I've " + ", ".join(changes) +
                ". You're still within the change window."
            ),
        }

    @staticmethod
    def get_recommendations(db: Session, restaurant_id: str, customer_id: Optional[str] = None, limit: int = 4) -> Dict[str, Any]:
        """Personalized recommendations (Module 10) using four signals:
        order history (favorite categories), spending pattern (preferred price
        tier), cuisine preference (cross-restaurant), and seasonal trends
        (current month). Falls back to popular items for new customers."""
        products = ProductRepository.list_by_restaurant(db, restaurant_id)
        available = [p for p in products if p.is_available]
        if not available:
            return {"basis": "our menu", "recommendations": []}

        favorite_categories: List[str] = []
        avg_spend = None
        fav_cuisine = None
        signals = []

        if customer_id:
            past = OrderRepository.list_by_customer(db, customer_id, restaurant_id)
            cat_counter: Counter = Counter()
            unit_prices: List[float] = []
            for o in past:
                for it in o.items:
                    prod = ProductRepository.get_by_id(db, it.product_id) if it.product_id else None
                    if prod:
                        cat_counter[prod.category] += it.quantity
                    if it.unit_price:
                        unit_prices.append(float(it.unit_price))
            favorite_categories = [c for c, _ in cat_counter.most_common(3)]
            if favorite_categories:
                signals.append("your order history")
            if unit_prices:
                avg_spend = sum(unit_prices) / len(unit_prices)
                signals.append("your spending pattern")

            # Cuisine preference — across ALL of the customer's orders (any restaurant).
            cuisine_counter: Counter = Counter()
            for o in OrderRepository.list_by_customer(db, customer_id):
                rest = RestaurantRepository.get_by_id(db, o.restaurant_id)
                if rest and rest.cuisine:
                    cuisine_counter[rest.cuisine] += 1
            if cuisine_counter:
                fav_cuisine = cuisine_counter.most_common(1)[0][0]

        this_rest = RestaurantRepository.get_by_id(db, restaurant_id)
        cuisine_match = bool(
            fav_cuisine and this_rest and this_rest.cuisine
            and fav_cuisine.lower() == this_rest.cuisine.lower()
        )
        if cuisine_match:
            signals.append(f"your taste for {fav_cuisine} food")

        # Seasonal trend: bias toward season-appropriate categories (current month).
        season_keywords = _seasonal_prefs()
        if season_keywords:
            signals.append("the season")

        def _score(p) -> float:
            s = 0.0
            if p.category in favorite_categories:
                s += 3.0
            if avg_spend is not None and 0.6 * avg_spend <= p.base_price <= 1.6 * avg_spend:
                s += 2.0
            cat_l = (p.category or "").lower()
            if any(k in cat_l for k in season_keywords):
                s += 1.5
            # Cuisine preference (Module 10 signal 2): when this restaurant matches
            # the customer's favorite cuisine, surface its standout dishes more
            # strongly so cuisine genuinely reorders the picks.
            if cuisine_match and p.is_popular:
                s += 1.5
            if p.is_popular:
                s += 1.0
            return s

        picks = sorted(available, key=lambda p: (-_score(p), p.name))[:limit]

        if signals:
            basis = ", ".join(signals[:-1]) + (" and " + signals[-1] if len(signals) > 1 else signals[0])
        else:
            basis = "our most popular items"
        return {
            "basis": basis,
            "recommendations": [
                {"name": p.name, "category": p.category, "base_price": p.base_price, "dietary_tags": p.dietary_tags or []}
                for p in picks
            ],
        }
