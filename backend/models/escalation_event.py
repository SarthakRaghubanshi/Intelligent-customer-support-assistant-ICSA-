import uuid
from sqlalchemy import Column, String, Text, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from backend.database.database import Base

class EscalationEvent(Base):
    __tablename__ = "escalation_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    reason = Column(String(255), nullable=False)
    status = Column(String(50), default="pending", nullable=False, index=True) # pending, claimed, resolved
    priority = Column(String(20), default="medium", nullable=False, index=True) # low, medium, high
    notes = Column(Text, nullable=True)
    assigned_to = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolution_summary = Column(Text, nullable=True)
    resolved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    claimed_at = Column(DateTime, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="escalation_event")
    assigned_agent = relationship("User", foreign_keys=[assigned_to])
    resolved_agent = relationship("User", foreign_keys=[resolved_by])
