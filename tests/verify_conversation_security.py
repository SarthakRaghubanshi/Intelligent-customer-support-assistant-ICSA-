import os
import sys

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Isolated test DB setup
test_db_path = os.path.join(project_root, "data", "test_conversation_security.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass

from tests.utils.test_bootstrap import bootstrap_test_database, bootstrap_restaurant
from backend.repositories.conversation_repository import ConversationRepository
from backend.services.conversation_service import ConversationService
from backend.services.feedback_service import FeedbackService
from backend.models.user import User, UserRole

def run_tests():
    print("================================================================================")
    print("RUNNING CONVERSATION SECURITY & TRANSITION BOUNDARY TESTS")
    print("================================================================================")
    
    SessionLocalTest = bootstrap_test_database(os.environ["DATABASE_URL"])
    db = SessionLocalTest()
    
    try:
        # 1. Seed Restaurant and Customers
        rest = bootstrap_restaurant(db, "Security_Rest_ID", "Security Restaurant")
        
        customer_a = User(email="customer_a@test.com", hashed_password="hashed_password", role=UserRole.CUSTOMER)
        customer_b = User(email="customer_b@test.com", hashed_password="hashed_password", role=UserRole.CUSTOMER)
        db.add_all([customer_a, customer_b])
        db.commit()
        db.refresh(customer_a)
        db.refresh(customer_b)
        
        # 2. Create Conversation for Customer A
        conv_a = ConversationService.start_new_session(db, customer_id=customer_a.id, restaurant_id=rest.id)
        
        # 3. Customer A accesses history - succeeds
        print("Testing authorized customer access history...")
        history_a = ConversationService.load_history(db, conv_a.id, customer_a.id)
        assert isinstance(history_a, list)
        print("✓ Authorized history load succeeded.")
        
        # 4. Customer B accesses Customer A's history - blocked (PermissionError)
        print("Testing unauthorized customer access history...")
        try:
            ConversationService.load_history(db, conv_a.id, customer_b.id)
            assert False, "Failed: Allowed unauthorized customer history access"
        except PermissionError as e:
            assert "Access denied" in str(e)
            print("✓ Unauthorized history load correctly blocked.")
            
        # 5. Customer B submits feedback for Customer A's conversation - blocked
        print("Testing unauthorized feedback submission...")
        try:
            FeedbackService.submit_feedback(
                db=db,
                conversation_id=conv_a.id,
                rating=5,
                feedback_text="Hack text",
                customer_id=customer_b.id
            )
            assert False, "Failed: Allowed unauthorized feedback submission"
        except PermissionError as e:
            assert "Access denied" in str(e)
            print("✓ Unauthorized feedback submission correctly blocked.")
            
        # 6. Test state machine transition constraints
        print("Testing conversation status transition constraints...")
        # Valid: active -> escalated
        ConversationService.update_status(db, conv_a.id, "escalated")
        db.refresh(conv_a)
        assert conv_a.status == "escalated"
        print("✓ Transition 'active' -> 'escalated' allowed.")
        
        # Valid: escalated -> resolved
        ConversationService.update_status(db, conv_a.id, "resolved")
        db.refresh(conv_a)
        assert conv_a.status == "resolved"
        print("✓ Transition 'escalated' -> 'resolved' allowed.")
        
        # Invalid: resolved -> active (Blocked)
        print("Verifying resolved -> active is blocked...")
        try:
            ConversationService.update_status(db, conv_a.id, "active")
            assert False, "Failed: Allowed forbidden transition resolved -> active"
        except ValueError as e:
            assert "Forbidden status transition" in str(e)
            print("✓ Forbidden status transition resolved -> active correctly blocked.")
            
    finally:
        db.close()
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass
                
    print("\n✓ ALL CONVERSATION SECURITY & TRANSITION TESTS PASSED SUCCESSFULLY!")
    print("================================================================================\n")

if __name__ == "__main__":
    run_tests()
