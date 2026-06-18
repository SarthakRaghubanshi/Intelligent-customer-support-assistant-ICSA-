import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Float, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database.database import Base

class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    
    intent = Column(String(100), nullable=True)
    intent_confidence = Column(Float, nullable=True)
    
    sentiment = Column(String(50), nullable=True)
    sentiment_confidence = Column(Float, nullable=True)
    
    language = Column(String(50), nullable=True)
    language_code = Column(String(10), nullable=True)
    
    latency_ms = Column(Float, nullable=True)
    escalated = Column(Boolean, default=False, nullable=False)
    sources = Column(JSON, nullable=True)
    
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
