from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from backend.models.message import Message

class MessageRepository:
    @staticmethod
    def create(
        db: Session,
        conversation_id: str,
        role: str,
        content: str,
        intent: Optional[str] = None,
        intent_confidence: Optional[float] = None,
        sentiment: Optional[str] = None,
        sentiment_confidence: Optional[float] = None,
        language: Optional[str] = None,
        language_code: Optional[str] = None,
        latency_ms: Optional[float] = None,
        escalated: bool = False,
        sources: Optional[List[Dict[str, Any]]] = None
    ) -> Message:
        message = Message(
            conversation_id=conversation_id,
            role=role,
            content=content,
            intent=intent,
            intent_confidence=intent_confidence,
            sentiment=sentiment,
            sentiment_confidence=sentiment_confidence,
            language=language,
            language_code=language_code,
            latency_ms=latency_ms,
            escalated=escalated,
            sources=sources
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message

    @staticmethod
    def list_by_conversation(db: Session, conversation_id: str) -> List[Message]:
        return db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.timestamp.asc()).all()
