"""
End-to-end smoke test: drives the real AI pipeline (NLU -> escalation -> domain
routing / RAG -> Gemini) against the seeded database for several PRD modules.

Run: python -m scripts.smoke_test
Requires a seeded DB with a built vector index (python -m scripts.seed).
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from backend.database.database import SessionLocal
from backend.repositories.restaurant_repository import RestaurantRepository
from backend.repositories.user_repository import UserRepository
from backend.classifiers.intent_classifier import classify_intent
from backend.classifiers.sentiment_classifier import classify_sentiment
from backend.classifiers.language_detector import detect_language
from backend.services.conversation_orchestrator import ConversationOrchestrator

CASES = [
    ("Knowledge/FAQ (RAG)", "Do you offer a gluten-free crust option?"),
    ("Store info (RAG)", "What time do you close on Friday?"),
    ("Delivery (RAG)", "How much do you charge for delivery?"),
    ("Order status (domain)", "Where is my order #1254?"),
    ("Menu discovery (domain)", "Can you suggest some vegan options under 500?"),
    ("Multilingual (Hindi)", "Kya aap vegan pizza dete ho?"),
    ("Escalation + sentiment", "This is terrible, my pizza was cold and I want a full refund now!"),
]


def main():
    db = SessionLocal()
    pizza = RestaurantRepository.get_by_name(db, "Pizza Paradise")
    customer = UserRepository.get_by_email(db, "customer@icsa.com")
    if not pizza:
        print("No seeded restaurant found. Run: python -m scripts.seed")
        return

    for label, q in CASES:
        res = ConversationOrchestrator.orchestrate(
            db=db, restaurant_id=pizza.id, question=q,
            intent_classifier=classify_intent,
            sentiment_classifier=classify_sentiment,
            language_detector=detect_language,
            customer_id=customer.id,
        )
        esc = res["escalation_result"]
        print("\n" + "=" * 70)
        print(f"[{label}]  Q: {q}")
        print(f"  intent={res['intent']} | sentiment={res['sentiment']} | lang={res['language']} "
              f"| escalate={esc.get('escalate')} ({esc.get('reason')})")
        print(f"  answer: {res['answer'][:400]}")
    db.close()


if __name__ == "__main__":
    main()
