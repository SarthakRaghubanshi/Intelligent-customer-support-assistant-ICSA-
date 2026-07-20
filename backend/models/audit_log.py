import uuid
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.sql import func
from backend.database.database import Base


class AuditLog(Base):
    """
    Immutable audit trail of security-relevant actions (PRD Section 13 security /
    compliance): logins, escalation lifecycle, AI-config changes, document
    uploads. Append-only; supports accountability and basic GDPR-style traceability.
    """
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_user_id = Column(String(36), nullable=True)
    actor_email = Column(String(255), nullable=True)
    action = Column(String(100), nullable=False)        # e.g. "login", "escalation.resolve"
    entity_type = Column(String(100), nullable=True)    # e.g. "escalation", "restaurant"
    entity_id = Column(String(36), nullable=True)
    restaurant_id = Column(String(36), nullable=True, index=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
