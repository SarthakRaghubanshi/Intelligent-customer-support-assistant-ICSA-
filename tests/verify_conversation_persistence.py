import os
import sys

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Isolated test DB setup
test_db_path = os.path.join(project_root, "data", "test_conversation_persistence.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass

from tests.utils.test_bootstrap import bootstrap_test_database, bootstrap_restaurant
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.message_repository import MessageRepository
from backend.models.conversation import Conversation
from backend.models.message import Message

def run_tests():
    print("================================================================================")
    print("RUNNING CONVERSATION PERSISTENCE CRUD & CASCADE TESTS")
    print("================================================================================")
    
    SessionLocalTest = bootstrap_test_database(os.environ["DATABASE_URL"])
    db = SessionLocalTest()
    
    try:
        # 1. Seed Restaurant and User
        rest = bootstrap_restaurant(db, "Persist_Rest_ID", "Persist Restaurant")
        from backend.models.user import User, UserRole
        customer = User(email="customer_persist@test.com", hashed_password="hashed_password", role=UserRole.CUSTOMER)
        db.add(customer)
        db.commit()
        db.refresh(customer)
        
        # 2. Create Conversation Shell
        print("Creating Conversation shell...")
        conv = ConversationRepository.create(db, customer_id=customer.id, restaurant_id=rest.id)
        assert conv is not None
        assert conv.status == "active"
        assert conv.customer_id == customer.id
        assert conv.restaurant_id == rest.id
        print("✓ Conversation created successfully.")
        
        # 3. Create User Message
        print("Creating User Message turn...")
        msg_user = MessageRepository.create(
            db=db,
            conversation_id=conv.id,
            role="user",
            content="Do you have gluten-free pizza?"
        )
        assert msg_user is not None
        assert msg_user.role == "user"
        assert msg_user.content == "Do you have gluten-free pizza?"
        assert msg_user.conversation_id == conv.id
        print("✓ User Message created successfully.")
        
        # 4. Create Assistant Message with NLU metadata
        print("Creating Assistant Message turn with NLU metadata and sources...")
        sources = [
            {"document_id": "doc-gf-1", "title": "Menu Options", "document_type": "menu", "snippet": "Gluten-free crust contains cauliflower."}
        ]
        msg_assistant = MessageRepository.create(
            db=db,
            conversation_id=conv.id,
            role="assistant",
            content="Yes, we offer gluten-free crust for an extra ₹50.",
            intent="Menu Inquiry",
            intent_confidence=0.98,
            sentiment="Neutral",
            sentiment_confidence=0.95,
            language="English",
            language_code="en",
            latency_ms=120.5,
            escalated=False,
            sources=sources
        )
        assert msg_assistant is not None
        assert msg_assistant.role == "assistant"
        assert msg_assistant.intent == "Menu Inquiry"
        assert msg_assistant.intent_confidence == 0.98
        assert msg_assistant.latency_ms == 120.5
        assert msg_assistant.sources == sources
        print("✓ Assistant Message created successfully.")
        
        # 5. List and Verify Transcripts
        print("Listing conversation history...")
        history = MessageRepository.list_by_conversation(db, conv.id)
        assert len(history) == 2
        assert history[0].role == "user"
        assert history[1].role == "assistant"
        print("✓ Transcripts listed in chronological order successfully.")
        
        # 6. Verify Cascade Deletion
        print("Verifying cascade delete constraints...")
        db.delete(conv)
        db.commit()
        
        # Check messages are deleted
        msg_count = db.query(Message).filter(Message.conversation_id == conv.id).count()
        assert msg_count == 0, f"Expected 0 messages remaining, found {msg_count}"
        print("✓ Cascade deletion constraints verified successfully.")
        
    finally:
        db.close()
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass
    
    print("\n✓ ALL CONVERSATION PERSISTENCE TESTS PASSED SUCCESSFULLY!")
    print("================================================================================\n")

if __name__ == "__main__":
    run_tests()
