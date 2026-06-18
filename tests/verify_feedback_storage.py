import os
import sys

# Ensure project root is in path
current_file_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_file_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# Isolated test DB setup
test_db_path = os.path.join(project_root, "data", "test_feedback_storage.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"

if os.path.exists(test_db_path):
    try:
        os.remove(test_db_path)
    except Exception:
        pass

from tests.utils.test_bootstrap import bootstrap_test_database, bootstrap_restaurant
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.feedback_repository import FeedbackRepository
from backend.services.feedback_service import FeedbackService
from backend.models.customer_feedback import CustomerFeedback

def run_tests():
    print("================================================================================")
    print("RUNNING FEEDBACK STORAGE & VALIDATION TESTS")
    print("================================================================================")
    
    SessionLocalTest = bootstrap_test_database(os.environ["DATABASE_URL"])
    db = SessionLocalTest()
    
    try:
        # 1. Seed Restaurant and User
        rest = bootstrap_restaurant(db, "Feedback_Rest_ID", "Feedback Restaurant")
        from backend.models.user import User, UserRole
        customer = User(email="customer_feedback@test.com", hashed_password="hashed_password", role=UserRole.CUSTOMER)
        db.add(customer)
        db.commit()
        db.refresh(customer)
        
        # 2. Create Conversation
        conv = ConversationRepository.create(db, customer_id=customer.id, restaurant_id=rest.id)
        
        # 3. Submit valid feedback
        print("Submitting valid feedback (rating 5)...")
        feedback = FeedbackService.submit_feedback(
            db=db,
            conversation_id=conv.id,
            rating=5,
            feedback_text="Excellent support and prompt responses!",
            customer_id=customer.id
        )
        assert feedback is not None
        assert feedback.rating == 5
        assert feedback.feedback_text == "Excellent support and prompt responses!"
        
        # Check conversation status updated to resolved
        db.refresh(conv)
        assert conv.status == "resolved", f"Expected resolved status, found '{conv.status}'"
        print("✓ Valid feedback submitted and session resolved successfully.")
        
        # 4. Assert duplicate feedback fails
        print("Verifying duplicate feedback prevention...")
        try:
            FeedbackService.submit_feedback(
                db=db,
                conversation_id=conv.id,
                rating=4,
                feedback_text="Another comment",
                customer_id=customer.id
            )
            assert False, "Failed: Allowed duplicate feedback submissions"
        except ValueError as e:
            assert "already been submitted" in str(e)
            print("✓ Duplicate feedback correctly blocked.")
            
        # 5. Assert out of bounds rating fails (rating = 6)
        print("Verifying out of bounds rating validation (rating 6)...")
        conv_new = ConversationRepository.create(db, customer_id=customer.id, restaurant_id=rest.id)
        try:
            FeedbackService.submit_feedback(
                db=db,
                conversation_id=conv_new.id,
                rating=6,
                feedback_text="Too high",
                customer_id=customer.id
            )
            assert False, "Failed: Allowed out of bounds rating 6"
        except ValueError as e:
            assert "between 1 and 5" in str(e)
            print("✓ Rating > 5 correctly blocked.")

        # 6. Assert out of bounds rating fails (rating = 0)
        print("Verifying out of bounds rating validation (rating 0)...")
        try:
            FeedbackService.submit_feedback(
                db=db,
                conversation_id=conv_new.id,
                rating=0,
                feedback_text="Too low",
                customer_id=customer.id
            )
            assert False, "Failed: Allowed out of bounds rating 0"
        except ValueError as e:
            assert "between 1 and 5" in str(e)
            print("✓ Rating < 1 correctly blocked.")

    finally:
        db.close()
        if os.path.exists(test_db_path):
            try:
                os.remove(test_db_path)
            except Exception:
                pass
                
    print("\n✓ ALL FEEDBACK STORAGE & VALIDATION TESTS PASSED SUCCESSFULLY!")
    print("================================================================================\n")

if __name__ == "__main__":
    run_tests()
