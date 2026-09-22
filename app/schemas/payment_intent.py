import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class PaymentIntentCreate(BaseModel):
    customer_id: uuid.UUID
    account_id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    amount: Decimal = Field(..., gt=0)
    payment_method: str = Field(default="payment_link", max_length=50)
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class PaymentIntentSendLink(BaseModel):
    channel: str = Field(default="sms", max_length=50)  # sms, whatsapp, email
    recipient: Optional[str] = None


class PaymentIntentResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    account_id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    amount: Decimal
    payment_method: str
    status: str
    reference_id: Optional[str] = None
    link_url: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
