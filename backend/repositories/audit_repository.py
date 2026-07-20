from typing import Optional, List
from sqlalchemy.orm import Session
from backend.models.audit_log import AuditLog


class AuditRepository:
    @staticmethod
    def create(db: Session, action: str, actor_user_id: Optional[str] = None,
               actor_email: Optional[str] = None, entity_type: Optional[str] = None,
               entity_id: Optional[str] = None, restaurant_id: Optional[str] = None,
               detail: Optional[str] = None) -> AuditLog:
        row = AuditLog(
            action=action, actor_user_id=actor_user_id, actor_email=actor_email,
            entity_type=entity_type, entity_id=entity_id, restaurant_id=restaurant_id,
            detail=detail,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row

    @staticmethod
    def list_recent(db: Session, restaurant_id: Optional[str] = None, limit: int = 100) -> List[AuditLog]:
        q = db.query(AuditLog)
        if restaurant_id:
            q = q.filter(AuditLog.restaurant_id == restaurant_id)
        return q.order_by(AuditLog.created_at.desc()).limit(limit).all()
