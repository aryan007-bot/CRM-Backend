import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class CallbackCreate(BaseModel):
    customer_id: uuid.UUID
    account_id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    scheduled_time: datetime
    phone_number: str = Field(..., max_length=50)
    requested_by: str = Field(default="customer", max_length=50)
    notes: Optional[str] = None


class CallbackUpdate(BaseModel):
    scheduled_time: Optional[datetime] = None
    phone_number: Optional[str] = None
    status: Optional[str] = None  # pending, completed, missed, cancelled
    notes: Optional[str] = None


class CallbackResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    account_id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    scheduled_time: datetime
    phone_number: str
    status: str
    requested_by: str
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
