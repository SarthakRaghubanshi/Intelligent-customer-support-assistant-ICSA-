from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from backend.models.escalation_event import EscalationEvent
from backend.models.conversation import Conversation

class EscalationRepository:
    @staticmethod
    def create(db: Session, conversation_id: str, reason: str, priority: str) -> EscalationEvent:
        """
        Creates and persists a new EscalationEvent record.
        """
        escalation = EscalationEvent(
            conversation_id=conversation_id,
            reason=reason,
            priority=priority,
            status="pending"
        )
        db.add(escalation)
        db.commit()
        db.refresh(escalation)
        return escalation

    @staticmethod
    def get_by_id(db: Session, escalation_id: str) -> Optional[EscalationEvent]:
        """
        Retrieves an EscalationEvent by primary key.
        """
        return db.query(EscalationEvent).filter(EscalationEvent.id == escalation_id).first()

    @staticmethod
    def get_by_conversation(db: Session, conversation_id: str) -> Optional[EscalationEvent]:
        """
        Retrieves the EscalationEvent associated with a given conversation.
        """
        return db.query(EscalationEvent).filter(EscalationEvent.conversation_id == conversation_id).first()

    @staticmethod
    def list_by_restaurant(db: Session, restaurant_id: str) -> List[EscalationEvent]:
        """
        Lists all escalation events for a given restaurant, ordered by created_at DESC.
        """
        return db.query(EscalationEvent)\
            .join(Conversation, EscalationEvent.conversation_id == Conversation.id)\
            .filter(Conversation.restaurant_id == restaurant_id)\
            .order_by(EscalationEvent.created_at.desc())\
            .all()

    @staticmethod
    def list_by_status(db: Session, restaurant_id: str, status: str) -> List[EscalationEvent]:
        """
        Lists escalations for a restaurant filtered by status, ordered by created_at DESC.
        """
        return db.query(EscalationEvent)\
            .join(Conversation, EscalationEvent.conversation_id == Conversation.id)\
            .filter(Conversation.restaurant_id == restaurant_id, EscalationEvent.status == status)\
            .order_by(EscalationEvent.created_at.desc())\
            .all()

    @staticmethod
    def claim(db: Session, escalation_id: str, user_id: str) -> Optional[EscalationEvent]:
        """
        Updates status to 'claimed', updates assigned_to, and sets claimed_at timestamp.
        """
        escalation = EscalationRepository.get_by_id(db, escalation_id)
        if escalation:
            escalation.status = "claimed"
            escalation.assigned_to = user_id
            escalation.claimed_at = func.now()
            db.commit()
            db.refresh(escalation)
        return escalation

    @staticmethod
    def resolve(db: Session, escalation_id: str, user_id: str, summary: str) -> Optional[EscalationEvent]:
        """
        Updates status to 'resolved', sets resolution details and resolved_at.
        """
        escalation = EscalationRepository.get_by_id(db, escalation_id)
        if escalation:
            escalation.status = "resolved"
            escalation.resolved_by = user_id
            escalation.resolution_summary = summary
            escalation.resolved_at = func.now()
            db.commit()
            db.refresh(escalation)
        return escalation

    @staticmethod
    def update_notes(db: Session, escalation_id: str, notes: str) -> Optional[EscalationEvent]:
        """
        Updates the manager notes field.
        """
        escalation = EscalationRepository.get_by_id(db, escalation_id)
        if escalation:
            escalation.notes = notes
            db.commit()
            db.refresh(escalation)
        return escalation

    # Future Step 11 contracts implemented for test coverage
    @staticmethod
    def count_open_by_restaurant(db: Session, restaurant_id: str) -> int:
        return db.query(EscalationEvent)\
            .join(Conversation, EscalationEvent.conversation_id == Conversation.id)\
            .filter(Conversation.restaurant_id == restaurant_id, EscalationEvent.status.in_(["pending", "claimed"]))\
            .count()

    @staticmethod
    def count_resolved_by_restaurant(db: Session, restaurant_id: str) -> int:
        return db.query(EscalationEvent)\
            .join(Conversation, EscalationEvent.conversation_id == Conversation.id)\
            .filter(Conversation.restaurant_id == restaurant_id, EscalationEvent.status == "resolved")\
            .count()
