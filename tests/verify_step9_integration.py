import os
import sys
import unittest.mock as mock

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Isolated test DB setup
test_db_path = os.path.join(project_root, "data", "test_step9_integration.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass

from tests.utils.test_bootstrap import bootstrap_test_database, bootstrap_restaurant
from backend.services.conversation_service import ConversationService
from backend.services.feedback_service import FeedbackService
from backend.repositories.message_repository import MessageRepository
from backend.services.conversation_orchestrator import ConversationOrchestrator
from backend.models.user import User, UserRole

class MockResponse:
    def __init__(self, text):
        self.text = text

def mock_generate_content(*args, **kwargs):
    return MockResponse("This is a mock response from our unified support AI.")

def run_tests():
    print("================================================================================")
    print("RUNNING STEP 9 FULL INTEGRATED CONVERSATION & FEEDBACK LOOP")
    print("================================================================================")
    
    SessionLocalTest = bootstrap_test_database(os.environ["DATABASE_URL"])
    db = SessionLocalTest()
    
    try:
        # 1. Seed Restaurant and User
        rest = bootstrap_restaurant(db, "Integ_Rest_ID", "Integ Restaurant")
        customer = User(email="customer_integ@test.com", hashed_password="hashed_password", role=UserRole.CUSTOMER)
        db.add(customer)
        db.commit()
        db.refresh(customer)
        
        # 2. Start Conversation Session
        print("1. Starting conversation session...")
        conv = ConversationService.start_new_session(db, customer_id=customer.id, restaurant_id=rest.id)
        assert conv.status == "active"
        
        # 3. Simulate User sending Query
        query = "Can I get a refund? My pizza was cold."
        print(f"2. Simulating User sending query: '{query}'...")
        
        # Save User turn to database
        MessageRepository.create(
            db=db,
            conversation_id=conv.id,
            role="user",
            content=query
        )
        
        # 4. Invoke orchestrator and save Assistant turn
        print("3. Invoking unified orchestrator...")
        with mock.patch("google.generativeai.generative_models.GenerativeModel.generate_content", side_effect=mock_generate_content):
            res_orch = ConversationOrchestrator.orchestrate(
                db=db,
                restaurant_id=rest.id,
                question=query
            )
            
            # Save Assistant turn to database
            MessageRepository.create(
                db=db,
                conversation_id=conv.id,
                role="assistant",
                content=res_orch["answer"],
                intent=res_orch["intent"],
                intent_confidence=res_orch.get("intent_info", {}).get("confidence", 0.0),
                sentiment=res_orch["sentiment"],
                sentiment_confidence=res_orch.get("intent_info", {}).get("confidence", 0.0), # using confidence as placeholder
                language=res_orch["language"],
                language_code=res_orch["language_code"],
                latency_ms=150.0,
                escalated=res_orch["escalation_result"]["escalate"],
                sources=res_orch["sources"]
            )
            
            if res_orch["escalation_result"]["escalate"]:
                ConversationService.update_status(db, conv.id, "escalated")
                
        # Verify status is now escalated
        db.refresh(conv)
        assert conv.status == "escalated", f"Expected escalated, got '{conv.status}'"
        print("✓ Message turns persisted and status updated to escalated.")
        
        # 5. Submit CSAT Rating & Close Chat
        print("4. Submitting feedback (rating 4) and closing chat...")
        feedback = FeedbackService.submit_feedback(
            db=db,
            conversation_id=conv.id,
            rating=4,
            feedback_text="Manager resolved cold pizza issue nicely.",
            customer_id=customer.id
        )
        
        # Verify feedback persisted
        assert feedback is not None
        assert feedback.rating == 4
        assert feedback.feedback_text == "Manager resolved cold pizza issue nicely."
        
        # Verify conversation status is updated to resolved
        db.refresh(conv)
        assert conv.status == "resolved", f"Expected resolved status, got '{conv.status}'"
        print("✓ Feedback saved and conversation successfully closed.")
        
    finally:
        db.close()
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass
                
    print("\n✓ ALL STEP 9 INTEGRATED TESTS PASSED SUCCESSFULLY!")
    print("================================================================================\n")

if __name__ == "__main__":
    run_tests()
