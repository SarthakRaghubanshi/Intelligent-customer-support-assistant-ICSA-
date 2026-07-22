"""
Idempotent database seed for ICSA.

Creates the permanent admin, three demo restaurants (with managers), demo
customers, structured menus, sample orders, and loads each restaurant's
knowledge-base text files. By default it also builds the ChromaDB vector index
for every restaurant so RAG works immediately.

Usage:
    python -m scripts.seed                # seed data + build vector index
    python -m scripts.seed --skip-index   # seed data only (fast)

Safe to run repeatedly: existing rows are detected and left untouched.
"""
import os
import sys
import argparse
import random
from datetime import datetime, timezone, timedelta

# Ensure project root on path when run as a script.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.database.database import SessionLocal
from backend.core.config import Config
from backend.models.user import UserRole
from backend.repositories.user_repository import UserRepository
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.product_repository import ProductRepository
from backend.repositories.order_repository import OrderRepository
from backend.repositories.knowledge_repository import KnowledgeRepository

from scripts.menu_data import RESTAURANTS, PRODUCTS, KB_FILES

DATA_DIR = os.path.join(_ROOT, "data")

CUSTOMER = {"email": "customer@icsa.com", "password": "Customer123!", "first": "Priya", "last": "Sharma"}
MANAGER_PASSWORD = "Manager123!"
TAX_RATE = 0.0825
DELIVERY_FEE = 49.0


def _get_or_create_user(db, email, password, role, first, last, restaurant_id=None):
    user = UserRepository.get_by_email(db, email)
    if user:
        return user, False
    user = UserRepository.create(
        db=db, email=email, password_raw=password, role=role,
        first_name=first, last_name=last, restaurant_id=restaurant_id,
    )
    return user, True


def seed_admin(db):
    admin, created = _get_or_create_user(
        db, Config.ADMIN_EMAIL, Config.ADMIN_PASSWORD, UserRole.ADMIN, "Platform", "Admin"
    )
    print(f"  admin: {admin.email} {'(created)' if created else '(exists)'}")
    return admin


def seed_restaurant(db, meta):
    rest = RestaurantRepository.get_by_name(db, meta["name"])
    if not rest:
        rest = RestaurantRepository.create(
            db, meta["name"], phone=meta["phone"], address=meta["address"], description=meta["description"]
        )
        print(f"  restaurant: {rest.name} (created)")
    else:
        print(f"  restaurant: {rest.name} (exists)")

    # Always sync the operational profile fields.
    RestaurantRepository.update_profile(db, rest.id, {
        "contact_email": meta["contact_email"],
        "business_hours": meta["business_hours"],
        "delivery_available": True,
        "delivery_notes": meta["delivery_notes"],
        "phone": meta["phone"],
        "address": meta["address"],
        "description": meta["description"],
        "cuisine": meta.get("cuisine"),
        "delivery_zones": meta.get("delivery_zones"),
    })

    m = meta["manager"]
    _get_or_create_user(db, m["email"], MANAGER_PASSWORD, UserRole.RESTAURANT, m["first"], m["last"], restaurant_id=rest.id)
    return rest


def seed_products(db, rest, folder):
    if ProductRepository.count_by_restaurant(db, rest.id) > 0:
        print(f"    products: exist ({ProductRepository.count_by_restaurant(db, rest.id)})")
        return
    for p in PRODUCTS.get(folder, []):
        ProductRepository.create(
            db, restaurant_id=rest.id, name=p["name"], category=p["category"],
            base_price=p["base_price"], description=p.get("description"),
            size_prices=p.get("size_prices"), dietary_tags=p.get("dietary_tags"),
            allergens=p.get("allergens"), is_popular=p.get("is_popular", False),
        )
    print(f"    products: created {len(PRODUCTS.get(folder, []))}")


def seed_knowledge(db, rest, folder):
    if KnowledgeRepository.get_document_count(db, rest.id) > 0:
        print(f"    knowledge docs: exist ({KnowledgeRepository.get_document_count(db, rest.id)})")
        return
    folder_path = os.path.join(DATA_DIR, folder)
    created = 0
    for stem, (title, doc_type) in KB_FILES.items():
        path = os.path.join(folder_path, f"{stem}.txt")
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if content:
            KnowledgeRepository.create(db, restaurant_id=rest.id, title=title, content=content, document_type=doc_type)
            created += 1
    print(f"    knowledge docs: created {created}")


def _item(prod, size=None, qty=1):
    if size and prod.size_prices and size in prod.size_prices:
        unit = float(prod.size_prices[size])
    else:
        unit = float(prod.base_price)
    return {"product_id": prod.id, "product_name": prod.name, "size": size, "quantity": qty, "unit_price": unit}


def seed_orders(db, customer, restaurants_by_folder):
    """Create demo orders so order-status, modification, and recommendation
    flows have data. Keyed on stable order numbers for idempotency."""
    now = datetime.now(timezone.utc)
    pizza = restaurants_by_folder.get("Restaurant_A")
    burgers = restaurants_by_folder.get("Restaurant_B")
    if not pizza:
        return

    def prod(rest, name):
        for p in ProductRepository.list_by_restaurant(db, rest.id):
            if p.name == name:
                return p
        return None

    plans = []
    # #1254 — in preparation, ~20 min ETA (the PRD's canonical example).
    plans.append(dict(order_number="1254", restaurant=pizza, status="preparing", order_type="delivery",
                      placed_at=now - timedelta(minutes=8), estimated_ready_at=now + timedelta(minutes=20),
                      payment_status="paid", payment_method="Google Pay",
                      items=[_item(prod(pizza, "Margherita Royale"), "Large 16\"", 1), _item(prod(pizza, "Organic Lemonade"), None, 2)]))
    # #1301 — just placed, still within the 5-minute modification window.
    plans.append(dict(order_number="1301", restaurant=pizza, status="placed", order_type="delivery",
                      placed_at=now - timedelta(minutes=2), estimated_ready_at=now + timedelta(minutes=30),
                      payment_status="cod", payment_method="Cash on Delivery",
                      items=[_item(prod(pizza, "Ultimate Pepperoni Rush"), "Medium 12\"", 1)]))
    # #1180 — delivered 3 days ago (history / recommendations).
    plans.append(dict(order_number="1180", restaurant=pizza, status="delivered", order_type="delivery",
                      placed_at=now - timedelta(days=3), estimated_ready_at=now - timedelta(days=3, minutes=-25),
                      payment_status="paid", payment_method="Visa",
                      items=[_item(prod(pizza, "Four Cheese Garden"), "Medium 12\"", 1), _item(prod(pizza, "Signature Tiramisu"), None, 1)]))
    if burgers:
        plans.append(dict(order_number="2010", restaurant=burgers, status="completed", order_type="pickup",
                          placed_at=now - timedelta(days=5), estimated_ready_at=now - timedelta(days=5, minutes=-20),
                          payment_status="paid", payment_method="Mastercard",
                          items=[_item(prod(burgers, "Classic Smash Burger"), "Double", 1), _item(prod(burgers, "Hand-Cut Craft Fries"), None, 1)]))

    created = 0
    for plan in plans:
        if OrderRepository.get_by_number(db, plan["order_number"]):
            continue
        items = [i for i in plan["items"] if i]
        subtotal = sum(i["quantity"] * i["unit_price"] for i in items)
        tax = round(subtotal * TAX_RATE, 2)
        fee = DELIVERY_FEE if plan["order_type"] == "delivery" else 0.0
        OrderRepository.create(
            db, order_number=plan["order_number"], restaurant_id=plan["restaurant"].id,
            customer_id=customer.id, items=items, order_type=plan["order_type"], status=plan["status"],
            delivery_address="A-12, Sector 18, Noida" if plan["order_type"] == "delivery" else None,
            delivery_fee=fee, tax=tax, payment_method=plan["payment_method"], payment_status=plan["payment_status"],
            estimated_ready_at=plan["estimated_ready_at"], placed_at=plan["placed_at"],
        )
        created += 1
    print(f"  demo orders: created {created}")


def _naive_utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Sample chat turns per intent, used to populate a realistic conversation history.
_INTENT_TURNS = {
    "Menu Inquiry": [("Do you have any vegan options?", "Yes! We have several vegan dishes on the menu."),
                     ("What do you recommend?", "Our most popular items are a great place to start."),
                     ("Any gluten-free choices?", "We do offer gluten-free options — happy to help.")],
    "Delivery Inquiry": [("How much is delivery?", "Delivery fees depend on your distance zone."),
                         ("How long will delivery take?", "Typical delivery is 30–50 minutes depending on the zone.")],
    "Store Information": [("What time do you close today?", "Our closing time varies by day — I can check for you."),
                          ("Are you open on Sunday?", "Yes, we're open on Sunday with slightly shorter hours.")],
    "Pickup Inquiry": [("How does curbside pickup work?", "Park in a reserved spot and we'll bring it out."),
                       ("When can I collect my order?", "We'll text you when it's boxed and ready.")],
    "Order Tracking": [("Where is my order?", "Let me check the latest status of your order."),
                       ("Is my order confirmed?", "Yes, the restaurant has accepted your order.")],
    "Refund Inquiry": [("I want a refund, my order was wrong.", "I'm sorry about that — I'm escalating this to the team."),
                       ("How do I get my money back?", "Let me connect you with support to process a refund.")],
    "Complaint": [("My pizza arrived cold and late.", "I'm really sorry — I'm escalating this to a team member."),
                  ("Wrong order again, this is unacceptable.", "Apologies for the trouble — escalating this now.")],
    "General Greeting": [("Hi there!", "Hello! How can I help you today?"),
                         ("Hey", "Hi! What can I do for you?")],
}
_INTENT_WEIGHTS = [
    ("Menu Inquiry", 5), ("Delivery Inquiry", 4), ("Store Information", 4),
    ("Pickup Inquiry", 2), ("Order Tracking", 3), ("General Greeting", 2),
    ("Refund Inquiry", 2), ("Complaint", 2),
]
_ESCALATION_PRIORITY = {"Refund Request": "high", "Customer Complaint": "high", "Negative Sentiment": "medium"}


def seed_conversations(db, customer, restaurants):
    """Create a realistic 7-day conversation history (messages, escalations,
    CSAT feedback) so the analytics and review dashboards have real data."""
    from backend.models.conversation import Conversation
    from backend.models.message import Message
    from backend.models.customer_feedback import CustomerFeedback
    from backend.models.escalation_event import EscalationEvent

    rng = random.Random(42)
    weighted_intents = [i for i, w in _INTENT_WEIGHTS for _ in range(w)]
    total_created = 0

    for rest in restaurants:
        if db.query(Conversation).filter(Conversation.restaurant_id == rest.id).count() > 0:
            continue
        n = rng.randint(16, 22)
        for _ in range(n):
            intent = rng.choice(weighted_intents)
            days_ago = rng.randint(0, 6)
            ts = _naive_utc_now() - timedelta(days=days_ago, hours=rng.randint(0, 12), minutes=rng.randint(0, 59))

            if intent in ("Complaint", "Refund Inquiry"):
                sentiment = "Negative"
            elif intent == "General Greeting":
                sentiment = rng.choice(["Positive", "Neutral"])
            else:
                sentiment = rng.choices(["Neutral", "Positive", "Negative"], weights=[6, 3, 1])[0]
            language = rng.choices(["English", "Hindi", "Spanish"], weights=[8, 1, 1])[0]
            lang_code = {"English": "en", "Hindi": "hi", "Spanish": "es"}[language]
            escalate = intent in ("Complaint", "Refund Inquiry") or (sentiment == "Negative" and rng.random() < 0.5)

            status = "escalated" if escalate else rng.choices(["resolved", "active"], weights=[7, 3])[0]
            conv = Conversation(restaurant_id=rest.id, customer_id=customer.id, status=status)
            conv.created_at = ts
            conv.updated_at = ts
            db.add(conv)
            db.flush()

            user_text, asst_text = rng.choice(_INTENT_TURNS[intent])
            um = Message(conversation_id=conv.id, role="user", content=user_text, intent=intent,
                         intent_confidence=round(rng.uniform(0.75, 0.99), 2), sentiment=sentiment,
                         sentiment_confidence=round(rng.uniform(0.7, 0.98), 2), language=language,
                         language_code=lang_code, escalated=escalate)
            um.timestamp = ts
            am = Message(conversation_id=conv.id, role="assistant", content=asst_text,
                         latency_ms=round(rng.uniform(900, 2400), 1), escalated=escalate)
            am.timestamp = ts + timedelta(seconds=2)
            db.add_all([um, am])

            if escalate:
                reason = "Refund Request" if intent == "Refund Inquiry" else ("Customer Complaint" if intent == "Complaint" else "Negative Sentiment")
                est = EscalationEvent(conversation_id=conv.id, reason=reason,
                                      priority=_ESCALATION_PRIORITY.get(reason, "medium"),
                                      status=rng.choices(["pending", "claimed", "resolved"], weights=[4, 2, 4])[0])
                est.created_at = ts
                est.updated_at = ts
                db.add(est)

            # ~55% leave CSAT feedback, correlated with sentiment.
            if rng.random() < 0.55:
                if sentiment == "Negative":
                    rating = rng.choice([1, 2, 3])
                elif sentiment == "Positive":
                    rating = rng.choice([5, 5, 4])
                else:
                    rating = rng.choice([3, 4, 5])
                fb = CustomerFeedback(conversation_id=conv.id, rating=rating,
                                      feedback_text=None if rng.random() < 0.6 else "Thanks for the quick help!")
                fb.created_at = ts
                db.add(fb)
            total_created += 1
    db.commit()
    print(f"  demo conversations: created {total_created}")


def reindex(force=False):
    print("\nBuilding ChromaDB vector index (embeds knowledge base — may take a few minutes)...")
    from backend.rag.vector_store import sync_restaurant_knowledge_base
    db = SessionLocal()
    try:
        # Query fresh inside this session so instances are session-bound.
        for rest in RestaurantRepository.list_active(db):
            persist_dir = os.path.join(DATA_DIR, "chroma_db", rest.id)
            # Skip restaurants that are already indexed unless forced — keeps
            # container restarts fast and avoids re-spending the embedding quota.
            if not force and os.path.isdir(persist_dir) and os.listdir(persist_dir):
                print(f"  indexed: {rest.name} (already present, skipped)")
                continue
            try:
                sync_restaurant_knowledge_base(db, rest.id)
                print(f"  indexed: {rest.name}")
            except Exception as e:
                print(f"  index FAILED for {rest.name}: {e}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Seed the ICSA database.")
    parser.add_argument("--skip-index", action="store_true", help="Skip building the ChromaDB vector index.")
    parser.add_argument("--force-index", action="store_true", help="Rebuild the vector index even if it already exists.")
    args = parser.parse_args()

    print(f"Seeding database: {Config.DATABASE_URL}\n")
    db = SessionLocal()
    restaurants = []
    restaurants_by_folder = {}
    try:
        seed_admin(db)
        customer, _ = _get_or_create_user(db, CUSTOMER["email"], CUSTOMER["password"], UserRole.CUSTOMER, CUSTOMER["first"], CUSTOMER["last"])
        print(f"  customer: {customer.email}")

        for meta in RESTAURANTS:
            rest = seed_restaurant(db, meta)
            seed_products(db, rest, meta["folder"])
            seed_knowledge(db, rest, meta["folder"])
            restaurants.append(rest)
            restaurants_by_folder[meta["folder"]] = rest

        seed_orders(db, customer, restaurants_by_folder)
        seed_conversations(db, customer, restaurants)
        db.commit()
    finally:
        db.close()

    if not args.skip_index:
        reindex(force=args.force_index)

    print("\nSeed complete.")
    print("Accounts (all demo):")
    print(f"  Admin:    {Config.ADMIN_EMAIL} / {Config.ADMIN_PASSWORD}")
    print(f"  Customer: {CUSTOMER['email']} / {CUSTOMER['password']}")
    print(f"  Managers: manager.pizza@icsa.com / manager.burgers@icsa.com / manager.sushi@icsa.com  (pw: {MANAGER_PASSWORD})")


if __name__ == "__main__":
    main()
