from typing import Optional
from sqlalchemy.orm import Session
from backend.models.customer_feedback import CustomerFeedback
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.feedback_repository import FeedbackRepository
from backend.services.conversation_service import ConversationService

class FeedbackService:
    @staticmethod
    def submit_feedback(
        db: Session,
        conversation_id: str,
        rating: int,
        feedback_text: Optional[str],
        customer_id: Optional[str]
    ) -> CustomerFeedback:
        """
        Submits customer rating and comment feedback for a conversation,
        enforcing ownership bounds and state transition updates.
        """
        # 1. Validate CSAT range
        if not (1 <= rating <= 5):
            raise ValueError("CSAT Rating must be an integer between 1 and 5.")
            
        # 2. Check conversation presence
        conversation = ConversationRepository.get_by_id(db, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found.")
            
        # 3. Security Ownership Validation
        if conversation.customer_id != customer_id:
            raise PermissionError("Access denied: You do not own this conversation.")
            
        # 4. Check for duplicate feedback submissions
        existing_feedback = FeedbackRepository.get_by_conversation(db, conversation_id)
        if existing_feedback:
            raise ValueError("Feedback has already been submitted for this conversation.")
            
        # 5. Persist feedback
        feedback = FeedbackRepository.create(db, conversation_id, rating, feedback_text)
        
        # 6. Set conversation status to 'resolved' (using transition validation inside ConversationService)
        ConversationService.update_status(db, conversation_id, "resolved")
        
        return feedback
