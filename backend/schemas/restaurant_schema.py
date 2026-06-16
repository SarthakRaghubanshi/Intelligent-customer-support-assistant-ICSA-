import re
from typing import Optional, Dict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator

# Regex rules for email and time formatting checks
EMAIL_REGEX = re.compile(r'^[\w\.-]+@[\w\.-]+\.\w+$')
TIME_REGEX = re.compile(r"^([0-1][0-9]|2[0-3]):[0-5][0-9]$")

class BusinessHourDay(BaseModel):
    open: Optional[str] = None
    close: Optional[str] = None
    closed: bool = False

    @model_validator(mode="after")
    def validate_hours(self) -> "BusinessHourDay":
        if self.closed:
            # open and close may be omitted. If provided, check HH:MM format.
            if self.open is not None and not TIME_REGEX.match(self.open):
                raise ValueError("Time must be in HH:MM format (24-hour style, e.g. 09:30)")
            if self.close is not None and not TIME_REGEX.match(self.close):
                raise ValueError("Time must be in HH:MM format (24-hour style, e.g. 22:00)")
        else:
            # closed is False, open and close are required and must match HH:MM format
            if self.open is None or self.close is None:
                raise ValueError("Open and close times are required when restaurant is not closed on that day.")
            if not TIME_REGEX.match(self.open):
                raise ValueError("Open time must be in HH:MM format (24-hour style, e.g. 09:30)")
            if not TIME_REGEX.match(self.close):
                raise ValueError("Close time must be in HH:MM format (24-hour style, e.g. 22:00)")
        return self

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

class RestaurantProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    phone: Optional[str] = Field(None, max_length=50)
    address: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=500)
    contact_email: Optional[str] = Field(None, max_length=255)
    business_hours: Optional[Dict[str, BusinessHourDay]] = None
    delivery_available: Optional[bool] = None
    delivery_notes: Optional[str] = Field(None, max_length=500)
    status_message: Optional[str] = Field(None, max_length=255)

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == "":
            return None
        v = v.strip().lower()
        if not EMAIL_REGEX.match(v):
            raise ValueError("Invalid email format")
        return v

    @field_validator("business_hours")
    @classmethod
    def validate_business_days(cls, v: Optional[Dict[str, BusinessHourDay]]) -> Optional[Dict[str, BusinessHourDay]]:
        if v is None:
            return v
        valid_days = {"Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"}
        for day in v.keys():
            normalized_day = day.strip().capitalize()
            if normalized_day not in valid_days:
                raise ValueError(f"Invalid day: '{day}'. Must be a valid day of the week.")
        return v

class RestaurantProfileResponse(BaseModel):
    id: str
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    description: Optional[str] = None
    contact_email: Optional[str] = None
    business_hours: Optional[Dict[str, BusinessHourDay]] = None
    delivery_available: bool
    delivery_notes: Optional[str] = None
    status_message: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Configure Pydantic V2 to work with SQLAlchemy database objects
    model_config = ConfigDict(from_attributes=True)
