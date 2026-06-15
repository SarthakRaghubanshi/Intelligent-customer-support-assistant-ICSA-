from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class RestaurantBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=500)

class RestaurantCreate(RestaurantBase):
    pass

class RestaurantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None

class RestaurantResponse(RestaurantBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Configure Pydantic V2 to work with SQLAlchemy database objects
    model_config = ConfigDict(from_attributes=True)
