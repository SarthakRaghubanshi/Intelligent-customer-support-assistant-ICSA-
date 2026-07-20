from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy import func
from sqlalchemy.orm import Session
from backend.repositories.product_repository import ProductRepository
from backend.models.order import Order, OrderItem


def _product_to_dict(p) -> Dict[str, Any]:
    return {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "category": p.category,
        "base_price": p.base_price,
        "size_prices": p.size_prices,
        "dietary_tags": p.dietary_tags or [],
        "allergens": p.allergens or [],
        "is_popular": p.is_popular,
        "is_available": p.is_available,
    }


def _min_price(p: Dict[str, Any]) -> float:
    prices = [p["base_price"]] if p.get("base_price") else []
    if p.get("size_prices"):
        prices.extend([v for v in p["size_prices"].values() if isinstance(v, (int, float))])
    return min(prices) if prices else 0.0


class MenuService:
    """Menu Discovery Assistant (PRD Module 4). Structured filtering of a
    restaurant's menu by dietary preference, price/budget, category, and
    popularity. Always tenant-scoped by restaurant_id."""

    @staticmethod
    def list_products(db: Session, restaurant_id: str, only_available: bool = True) -> List[Dict[str, Any]]:
        return [_product_to_dict(p) for p in ProductRepository.list_by_restaurant(db, restaurant_id, only_available=only_available)]

    @staticmethod
    def discover(
        db: Session,
        restaurant_id: str,
        dietary: Optional[str] = None,
        max_price: Optional[float] = None,
        category: Optional[str] = None,
        popular_only: bool = False,
        keyword: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Return products matching the given filters (all optional / AND-combined)."""
        products = MenuService.list_products(db, restaurant_id)
        results = []
        for p in products:
            if dietary:
                tags = [str(t).lower() for t in p["dietary_tags"]]
                d = dietary.lower().strip()
                # "gluten free" / "gluten-free" tolerance
                if not any(d in t or t in d for t in tags):
                    continue
            if category and category.lower().strip() not in p["category"].lower():
                continue
            if popular_only and not p["is_popular"]:
                continue
            if max_price is not None and _min_price(p) > float(max_price):
                continue
            if keyword:
                hay = f"{p['name']} {p.get('description') or ''}".lower()
                if keyword.lower().strip() not in hay:
                    continue
            results.append(p)
        return results

    @staticmethod
    def popular_today(db: Session, restaurant_id: str, days: int = 30, limit: int = 10) -> List[Dict[str, Any]]:
        """"Most popular" by actual recent order quantity (PRD Module 4 example
        "what is most popular today"). Falls back to the curated is_popular flag
        when there is no recent order data."""
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        rows = (
            db.query(OrderItem.product_id, func.sum(OrderItem.quantity).label("q"))
            .join(Order, OrderItem.order_id == Order.id)
            .filter(
                Order.restaurant_id == restaurant_id,
                Order.placed_at >= since,
                OrderItem.product_id.isnot(None),
            )
            .group_by(OrderItem.product_id)
            .order_by(func.sum(OrderItem.quantity).desc())
            .limit(limit)
            .all()
        )
        ranked = []
        for pid, _q in rows:
            p = ProductRepository.get_by_id(db, pid)
            if p and p.is_available:
                ranked.append(_product_to_dict(p))
        if ranked:
            return ranked
        # No recent orders — fall back to the curated popularity flag.
        return [p for p in MenuService.list_products(db, restaurant_id) if p.get("is_popular")]

    @staticmethod
    def format_for_prompt(products: List[Dict[str, Any]], limit: int = 25) -> str:
        """Render a compact, factual menu listing that can be handed to the LLM
        as grounded context (prices included so it never invents them)."""
        if not products:
            return "No matching menu items were found."
        lines = []
        for p in products[:limit]:
            if p.get("size_prices"):
                price_str = ", ".join(f"{k}: ₹{v}" for k, v in p["size_prices"].items())
            else:
                price_str = f"₹{p['base_price']:.0f}"
            tags = f" [{', '.join(p['dietary_tags'])}]" if p["dietary_tags"] else ""
            popular = " (popular)" if p["is_popular"] else ""
            lines.append(f"- {p['name']} ({p['category']}){tags}{popular}: {price_str}")
        return "\n".join(lines)
