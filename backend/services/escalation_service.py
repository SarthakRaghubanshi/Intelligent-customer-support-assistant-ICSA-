from typing import Optional, List, Any
from sqlalchemy.orm import Session
from backend.models.escalation_event import EscalationEvent
from backend.models.user import User, UserRole
from backend.models.conversation import Conversation
from backend.repositories.escalation_repository import EscalationRepository
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.message_repository import MessageRepository
from backend.services.conversation_service import ConversationService
from backend.core.tenant import verify_tenant_access

class EscalationService:
    PRIORITY_MAP = {
        "Refund Request": "high",
        "Customer Complaint": "high",
        "Human Assistance Requested": "high",
        "Negative Sentiment": "medium",
        "Low Confidence": "low"
    }

    @staticmethod
    def _determine_priority(reason: str) -> str:
        """
        Maps escalation reason string to a priority bucket.
        """
        return EscalationService.PRIORITY_MAP.get(reason, "low")

    @staticmethod
    def create_escalation(db: Session, conversation_id: str, reason: str, priority: Optional[str] = None) -> EscalationEvent:
        """
        Idempotently creates a new escalation event and syncs conversation status.
        """
        # Check if one already exists (idempotency constraint)
        existing = EscalationRepository.get_by_conversation(db, conversation_id)
        if existing:
            return existing

        resolved_priority = priority or EscalationService._determine_priority(reason)
        
        # Check if conversation exists
        conversation = ConversationRepository.get_by_id(db, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        # Persist escalation
        escalation = EscalationRepository.create(db, conversation_id, reason, resolved_priority)

        # Sync conversation status to escalated
        ConversationService.update_status(db, conversation_id, "escalated")

        return escalation

    @staticmethod
    def claim_escalation(db: Session, escalation_id: str, user: User) -> EscalationEvent:
        """
        Allows a manager to claim a pending escalation case.
        """
        escalation = EscalationRepository.get_by_id(db, escalation_id)
        if not escalation:
            raise ValueError("Escalation not found")

        # Get conversation for tenant validation
        conversation = ConversationRepository.get_by_id(db, escalation.conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        # Enforce multi-tenant and role validation
        verify_tenant_access(user, conversation.restaurant_id)

        if user.role == UserRole.CUSTOMER:
            raise PermissionError("Customers cannot access the escalation board")

        # State machine transition checks
        if escalation.status != "pending":
            raise ValueError(f"Invalid escalation transition: {escalation.status} -> claimed")

        # Persist change
        updated = EscalationRepository.claim(db, escalation_id, user.id)
        if not updated:
            raise RuntimeError("Failed to claim escalation")
        return updated

    @staticmethod
    def resolve_escalation(db: Session, escalation_id: str, user: User, resolution_summary: str) -> EscalationEvent:
        """
        Allows the assigned manager to resolve an active escalation case.
        """
        escalation = EscalationRepository.get_by_id(db, escalation_id)
        if not escalation:
            raise ValueError("Escalation not found")

        conversation = ConversationRepository.get_by_id(db, escalation.conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        # Enforce multi-tenant and role validation
        verify_tenant_access(user, conversation.restaurant_id)

        if user.role == UserRole.CUSTOMER:
            raise PermissionError("Customers cannot access the escalation board")

        # State machine transition checks
        if escalation.status != "claimed":
            raise ValueError(f"Invalid escalation transition: {escalation.status} -> resolved")

        # Ownership validation check (Only the assigned agent can resolve)
        if escalation.assigned_to != user.id:
            raise PermissionError("Only the assigned manager may resolve this escalation")

        # Persist resolve status
        updated = EscalationRepository.resolve(db, escalation_id, user.id, resolution_summary)
        if not updated:
            raise RuntimeError("Failed to resolve escalation")

        # Sync conversation status to resolved
        ConversationService.update_status(db, conversation.id, "resolved")

        return updated

    @staticmethod
    def add_notes(db: Session, escalation_id: str, user: User, notes: str) -> EscalationEvent:
        """
        Adds internal notes to an escalation event.
        """
        escalation = EscalationRepository.get_by_id(db, escalation_id)
        if not escalation:
            raise ValueError("Escalation not found")

        conversation = ConversationRepository.get_by_id(db, escalation.conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        # Enforce multi-tenant check
        verify_tenant_access(user, conversation.restaurant_id)

        if user.role == UserRole.CUSTOMER:
            raise PermissionError("Customers cannot access the escalation board")

        # Check immutability
        if escalation.status == "resolved":
            raise ValueError("Resolved escalations are immutable")

        updated = EscalationRepository.update_notes(db, escalation_id, notes)
        if not updated:
            raise RuntimeError("Failed to update notes")
        return updated

    @staticmethod
    def get_escalations_for_restaurant(db: Session, user: User) -> List[EscalationEvent]:
        """
        Lists escalations for a restaurant, enforcing tenant bounds.
        """
        if user.role == UserRole.CUSTOMER:
            raise PermissionError("Customers cannot access the escalation board")

        if user.role == UserRole.ADMIN:
            return db.query(EscalationEvent).order_by(EscalationEvent.created_at.desc()).all()

        if not user.restaurant_id:
            raise ValueError("User has no restaurant assigned")

        return EscalationRepository.list_by_restaurant(db, user.restaurant_id)

    @staticmethod
    def get_transcript(db: Session, escalation_id: str, user: User) -> List[Any]:
        """
        Returns the chat transcript for the conversation attached to this escalation event.
        """
        escalation = EscalationRepository.get_by_id(db, escalation_id)
        if not escalation:
            raise ValueError("Escalation not found")

        conversation = ConversationRepository.get_by_id(db, escalation.conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")

        verify_tenant_access(user, conversation.restaurant_id)

        if user.role == UserRole.CUSTOMER:
            raise PermissionError("Customers cannot access the escalation board")

        return MessageRepository.list_by_conversation(db, conversation.id)
