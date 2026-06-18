from typing import Optional
from sqlalchemy.orm import Session
from backend.models.customer_feedback import CustomerFeedback

class FeedbackRepository:
    @staticmethod
    def create(db: Session, conversation_id: str, rating: int, feedback_text: Optional[str]) -> CustomerFeedback:
        if not (1 <= rating <= 5):
            raise ValueError("CSAT Rating must be an integer between 1 and 5.")
            
        feedback = CustomerFeedback(
            conversation_id=conversation_id,
            rating=rating,
            feedback_text=feedback_text
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback

    @staticmethod
    def get_by_conversation(db: Session, conversation_id: str) -> Optional[CustomerFeedback]:
        return db.query(CustomerFeedback).filter(
            CustomerFeedback.conversation_id == conversation_id
        ).first()
