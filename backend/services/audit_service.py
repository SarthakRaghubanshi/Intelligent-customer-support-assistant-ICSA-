"""
Audit logging (PRD Section 13 — security / accountability). Records
security-relevant actions to the audit_logs table. Failures never break the
calling flow.
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from backend.repositories.audit_repository import AuditRepository
from backend.models.audit_log import AuditLog


class AuditService:
    @staticmethod
    def log(db: Session, action: str, actor_user_id: Optional[str] = None,
            actor_email: Optional[str] = None, entity_type: Optional[str] = None,
            entity_id: Optional[str] = None, restaurant_id: Optional[str] = None,
            detail: Optional[str] = None) -> Optional[AuditLog]:
        try:
            return AuditRepository.create(
                db, action=action, actor_user_id=actor_user_id, actor_email=actor_email,
                entity_type=entity_type, entity_id=entity_id, restaurant_id=restaurant_id,
                detail=detail,
            )
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    def list_recent(db: Session, restaurant_id: Optional[str] = None, limit: int = 100) -> List[AuditLog]:
        return AuditRepository.list_recent(db, restaurant_id, limit)
