from typing import Optional, List
from sqlalchemy.orm import Session
from backend.models.conversation import Conversation

class ConversationRepository:
    @staticmethod
    def create(db: Session, customer_id: Optional[str], restaurant_id: str) -> Conversation:
        conversation = Conversation(
            customer_id=customer_id,
            restaurant_id=restaurant_id,
            status="active"
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        return conversation

    @staticmethod
    def get_by_id(db: Session, conversation_id: str) -> Optional[Conversation]:
        return db.query(Conversation).filter(Conversation.id == conversation_id).first()

    @staticmethod
    def update_status(db: Session, conversation_id: str, status: str) -> Optional[Conversation]:
        conversation = ConversationRepository.get_by_id(db, conversation_id)
        if conversation:
            conversation.status = status
            db.commit()
            db.refresh(conversation)
        return conversation

    @staticmethod
    def list_by_customer(db: Session, customer_id: str) -> List[Conversation]:
        return db.query(Conversation).filter(
            Conversation.customer_id == customer_id
        ).order_by(Conversation.created_at.desc()).all()

    @staticmethod
    def list_by_restaurant(db: Session, restaurant_id: str) -> List[Conversation]:
        return db.query(Conversation).filter(
            Conversation.restaurant_id == restaurant_id
        ).order_by(Conversation.created_at.desc()).all()
