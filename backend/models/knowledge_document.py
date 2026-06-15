import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database.database import Base

class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    # UUID Primary Key String
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Foreign key referencing Restaurant ID (nullable=False, indexed)
    restaurant_id = Column(String(36), ForeignKey("restaurants.id"), nullable=False, index=True)
    
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    document_type = Column(String(100), nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now(), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to Restaurant
    restaurant = relationship("Restaurant", back_populates="knowledge_documents")
