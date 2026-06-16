import uuid
from sqlalchemy import Column, String, Boolean, DateTime, JSON, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database.database import Base

class Restaurant(Base):
    __tablename__ = "restaurants"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(50), nullable=True)
    address = Column(String(255), nullable=True)
    description = Column(String(500), nullable=True)
    
    # New Profile operational fields
    contact_email = Column(String(255), nullable=True)
    business_hours = Column(JSON, nullable=True)
    delivery_available = Column(Boolean, default=True, server_default=text('1'), nullable=False)
    delivery_notes = Column(String(500), nullable=True)
    status_message = Column(String(255), nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)

    # Relationship to Users
    users = relationship("User", back_populates="restaurant")
    
    # Relationship to Knowledge Documents (no cascade delete)
    knowledge_documents = relationship("KnowledgeDocument", back_populates="restaurant")
