from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class KnowledgeDocumentBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    document_type: str = Field(..., min_length=1, max_length=100)

class KnowledgeDocumentCreate(KnowledgeDocumentBase):
    restaurant_id: str = Field(..., min_length=1, max_length=36)

class KnowledgeDocumentUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    content: Optional[str] = Field(None, min_length=1)
    document_type: Optional[str] = Field(None, min_length=1, max_length=100)

class KnowledgeDocumentResponse(KnowledgeDocumentBase):
    id: str
    restaurant_id: str
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
