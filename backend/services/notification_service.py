"""
Notification service — the integration point for Email / SMS / Push
(PRD Section 14). This build does not call an external provider; instead it logs
the alert and records an audit entry, so the hook exists and is observable. Swap
the body of `_dispatch` for a real provider (SendGrid, Twilio, FCM, …) in
production.
"""
import sys
from typing import Optional
from sqlalchemy.orm import Session

from backend.services.audit_service import AuditService


class NotificationService:

    @staticmethod
    def _dispatch(channel: str, message: str) -> None:
        # Integration point: replace with a real Email/SMS/Push provider call.
        print(f"[NOTIFY:{channel}] {message}", file=sys.stderr)

    @staticmethod
    def notify_escalation(db: Session, escalation, restaurant_id: Optional[str] = None) -> None:
        """Alert restaurant staff that a conversation was escalated."""
        reason = getattr(escalation, "reason", "Escalation")
        priority = getattr(escalation, "priority", "medium")
        esc_id = getattr(escalation, "id", None)
        message = f"New {priority}-priority ticket for restaurant staff: {reason} (escalation {esc_id})."
        for channel in ("email", "push"):
            NotificationService._dispatch(channel, message)
        AuditService.log(
            db, action="notification.escalation", entity_type="escalation",
            entity_id=esc_id, restaurant_id=restaurant_id, detail=message,
        )
