from typing import Optional, List
from sqlalchemy.orm import Session
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.repositories.conversation_repository import ConversationRepository
from backend.repositories.message_repository import MessageRepository
from backend.core.tenant import verify_restaurant_active

class ConversationService:
    @staticmethod
    def start_new_session(db: Session, customer_id: Optional[str], restaurant_id: str) -> Conversation:
        """
        Initializes a new support conversation session for the active tenant.
        """
        # Verify tenant is active
        verify_restaurant_active(db, restaurant_id)
        
        # Create conversation
        return ConversationRepository.create(db, customer_id, restaurant_id)

    @staticmethod
    def load_history(db: Session, conversation_id: str, customer_id: Optional[str]) -> List[Message]:
        """
        Loads the history transcripts for a specific conversation session,
        enforcing security ownership constraints.
        """
        conversation = ConversationRepository.get_by_id(db, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
            
        # Security validation: Verify the customer_id matches conversation owner
        # If user is not an admin/manager (we're at customer panel scope), verify ownership
        if conversation.customer_id != customer_id:
            raise PermissionError("Access denied: You do not own this conversation.")
            
        return MessageRepository.list_by_conversation(db, conversation_id)

    @staticmethod
    def update_status(db: Session, conversation_id: str, new_status: str) -> Conversation:
        """
        Transitions conversation status following the status state machine rules.
        """
        conversation = ConversationRepository.get_by_id(db, conversation_id)
        if not conversation:
            raise ValueError("Conversation not found")
            
        old_status = conversation.status
        if old_status == new_status:
            return conversation
            
        # Allowed transitions:
        # active -> escalated
        # active -> resolved
        # escalated -> resolved
        allowed = False
        if old_status == "active" and new_status in ["escalated", "resolved"]:
            allowed = True
        elif old_status == "escalated" and new_status == "resolved":
            allowed = True
            
        if not allowed:
            raise ValueError(f"Forbidden status transition from '{old_status}' to '{new_status}'")
            
        updated = ConversationRepository.update_status(db, conversation_id, new_status)
        if not updated:
            raise RuntimeError("Failed to update status")
        return updated
