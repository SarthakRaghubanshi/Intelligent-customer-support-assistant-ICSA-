import os
import sys

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Isolated test DB setup
test_db_path = os.path.join(project_root, "data", "test_transcript_retrieval.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass

from tests.utils.test_bootstrap import bootstrap_test_database, bootstrap_restaurant
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.message_repository import MessageRepository
from backend.models.user import User, UserRole

def run_tests():
    print("================================================================================")
    print("RUNNING TRANSCRIPT RETRIEVAL AUDIT TESTS")
    print("================================================================================")
    
    SessionLocalTest = bootstrap_test_database(os.environ["DATABASE_URL"])
    db = SessionLocalTest()
    
    try:
        # 1. Seed Restaurant and Customer
        rest = bootstrap_restaurant(db, "Audit_Rest_ID", "Audit Restaurant")
        customer = User(email="customer_audit@test.com", hashed_password="hashed_password", role=UserRole.CUSTOMER)
        db.add(customer)
        db.commit()
        db.refresh(customer)
        
        # 2. Create Conversation
        conv = ConversationRepository.create(db, customer_id=customer.id, restaurant_id=rest.id)
        
        # 3. Add Message sequence
        MessageRepository.create(
            db=db,
            conversation_id=conv.id,
            role="user",
            content="Can I speak to a manager?"
        )
        MessageRepository.create(
            db=db,
            conversation_id=conv.id,
            role="assistant",
            content="Let me help escalate this for you.",
            intent="Escalation Request",
            intent_confidence=0.99,
            sentiment="Negative",
            sentiment_confidence=0.85,
            language="English",
            language_code="en",
            latency_ms=150.0,
            escalated=True
        )
        
        # 4. Fetch Transcript and verify all details are returned
        print("Retrieving escalation transcript for audit...")
        messages = MessageRepository.list_by_conversation(db, conv.id)
        assert len(messages) == 2
        
        # User message verification
        assert messages[0].role == "user"
        assert messages[0].content == "Can I speak to a manager?"
        
        # Assistant message verification
        assert messages[1].role == "assistant"
        assert messages[1].intent == "Escalation Request"
        assert messages[1].intent_confidence == 0.99
        assert messages[1].sentiment == "Negative"
        assert messages[1].sentiment_confidence == 0.85
        assert messages[1].latency_ms == 150.0
        assert messages[1].escalated is True
        print("✓ All metadata fields accurately returned in transcript list.")
        
    finally:
        db.close()
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass
                
    print("\n✓ ALL TRANSCRIPT RETRIEVAL AUDIT TESTS PASSED SUCCESSFULLY!")
    print("================================================================================\n")

if __name__ == "__main__":
    run_tests()
