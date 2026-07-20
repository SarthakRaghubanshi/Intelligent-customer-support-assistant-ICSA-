"""
Domain router for the AI assistant.

Some customer questions must be answered from live structured data rather than
the (static) knowledge base:

  * Order Status (PRD Module 3)      -> the orders table, deterministically
  * Order Modification (Module 6)    -> the orders table + business rules
  * Menu Discovery (Module 4)        -> the products table (dietary/price/popular)
  * Personalized Recommendations (10)-> the customer's order history

`route()` inspects the classified intent and, when one of these applies, returns
a grounded answer dict. Returning None means "let the RAG knowledge pipeline
handle it" (FAQs, policies, delivery/pickup info, general questions).
"""
import re
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.services.order_service import OrderService, extract_order_number
from backend.services.menu_service import MenuService

# Query signals that a menu question is really a discovery / recommendation.
_DISCOVERY_RE = re.compile(
    r"\b(recommend|recommendation|suggest|suggestion|popular|best[\s-]?sell|"
    r"vegan|vegetarian|veggie|gluten|dairy[\s-]?free|budget|cheap|affordable|"
    r"under|below|less than|what should i|for me|my usual|favou?rite)\b",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"(?:under|below|less than|up\s*to|upto|within|max|budget of)\s*₹?\s*(\d{2,5})", re.IGNORECASE)
_PERSONAL_RE = re.compile(r"\b(recommend|suggest|for me|what should i|my usual|based on my|favou?rite)\b", re.IGNORECASE)


def _detect_dietary(text: str) -> Optional[str]:
    t = text.lower()
    if "vegan" in t or "dairy-free" in t or "dairy free" in t:
        return "vegan"
    if "gluten" in t:
        return "gluten-free"
    if "vegetarian" in t or "veggie" in t or re.search(r"\bveg\b", t):
        return "vegetarian"
    return None


# Query keyword -> menu category substring (cuisine/section discovery, Module 4).
_CATEGORY_MAP = [
    (r"\bpizzas?\b", "pizza"),
    (r"\bburgers?\b", "burger"),
    (r"\bpastas?\b", "pasta"),
    (r"\bramen\b", "ramen"),
    (r"\b(sushi|rolls?|maki)\b", "sushi"),
    (r"\b(dessert|sweet|cake|tiramisu)\b", "dessert"),
    (r"\b(drink|beverage|shake|lemonade|soda)\b", "beverage"),
    (r"\b(side|fries|starter|appetizer)\b", "side"),
]


def _detect_category(text: str) -> Optional[str]:
    for pattern, cat in _CATEGORY_MAP:
        if re.search(pattern, text, re.IGNORECASE):
            return cat
    return None


def _menu_answer(db: Session, restaurant_id: str, customer_id: Optional[str], question: str) -> Dict[str, Any]:
    dietary = _detect_dietary(question)
    price_m = _PRICE_RE.search(question)
    max_price = float(price_m.group(1)) if price_m else None
    wants_popular = bool(re.search(r"\bpopular|best[\s-]?sell\b", question, re.IGNORECASE))
    personal = bool(_PERSONAL_RE.search(question))

    # Personalized recommendation (no explicit filters) -> use order history.
    if personal and not dietary and max_price is None and not wants_popular:
        rec = OrderService.get_recommendations(db, restaurant_id, customer_id)
        if not rec["recommendations"]:
            return None  # empty menu -> fall back to RAG
        lines = [f"- {r['name']} ({r['category']}) — ₹{r['base_price']:.0f}" for r in rec["recommendations"]]
        answer = f"Based on {rec['basis']}, here are a few picks you might enjoy:\n" + "\n".join(lines)
        return {"answer": answer, "response_source": "Recommendation Engine", "sources": []}

    category = _detect_category(question)

    # "Most popular" with no other filters -> real order-based popularity.
    if wants_popular and not dietary and max_price is None and not category:
        products = MenuService.popular_today(db, restaurant_id)
    else:
        products = MenuService.discover(
            db, restaurant_id, dietary=dietary, max_price=max_price,
            category=category, popular_only=wants_popular,
        )
    if not products:
        # No structured match -> let RAG try the free-text menu instead of a dead end.
        return None
    listing = MenuService.format_for_prompt(products, limit=12)
    descriptor = []
    if dietary:
        descriptor.append(dietary)
    if category:
        descriptor.append(category)
    if wants_popular:
        descriptor.append("popular")
    if max_price is not None:
        descriptor.append(f"under ₹{int(max_price)}")
    label = (" ".join(descriptor) + " options") if descriptor else "menu items"
    answer = f"Here are some {label} for you:\n{listing}"
    return {"answer": answer, "response_source": "Menu Engine", "sources": []}


def route(
    db: Session,
    restaurant_id: str,
    customer_id: Optional[str],
    question: str,
    intent: str,
) -> Optional[Dict[str, Any]]:
    """Return a grounded domain answer, or None to defer to the RAG pipeline."""
    if intent == "Order Tracking":
        order_number = extract_order_number(question)
        if not customer_id and not order_number:
            return {
                "answer": "To check an order, please sign in with the account you ordered with, "
                          "or tell me your order number (e.g. #1254).",
                "response_source": "Order System", "sources": [],
            }
        res = OrderService.get_order_status(db, restaurant_id, customer_id, order_number)
        return {"answer": res["summary"], "response_source": "Order System", "sources": []}

    if intent == "Order Modification":
        order_number = extract_order_number(question)
        if not customer_id:
            return {"answer": "Please sign in so I can find and update your order.",
                    "response_source": "Order System", "sources": []}
        if not order_number:
            return {"answer": "Sure — what's the order number (e.g. #1254)? Note that changes are only "
                              "possible within 5 minutes of placing an order.",
                    "response_source": "Order System", "sources": []}
        res = OrderService.modify_order(db, restaurant_id, customer_id, order_number, question)
        return {"answer": res["summary"], "response_source": "Order System", "sources": []}

    if intent == "Delivery Inquiry":
        # Delivery-zone workflow (Section 10): if the customer states a distance,
        # validate the zone deterministically; otherwise defer to RAG.
        from backend.services.delivery_service import DeliveryService, extract_distance_km
        dist = extract_distance_km(question)
        if dist is not None:
            res = DeliveryService.check(db, restaurant_id, dist)
            if res:
                return {"answer": res["summary"], "response_source": "Delivery Zone Engine", "sources": []}
        return None

    if intent == "Menu Inquiry" and _DISCOVERY_RE.search(question):
        return _menu_answer(db, restaurant_id, customer_id, question)

    return None
