import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class PTPCreate(BaseModel):
    customer_id: uuid.UUID
    account_id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    outcome_id: Optional[uuid.UUID] = None
    amount: Decimal = Field(..., gt=0)
    promised_date: datetime
    grace_period_days: int = Field(default=2, ge=0, le=30)
    notes: Optional[str] = None


class PTPUpdate(BaseModel):
    status: Optional[str] = None  # active, kept, broken, cancelled
    notes: Optional[str] = None
    promised_date: Optional[datetime] = None
    grace_period_days: Optional[int] = Field(default=None, ge=0, le=30)


class PTPResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    account_id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    outcome_id: Optional[uuid.UUID] = None
    amount: Decimal
    promised_date: datetime
    status: str
    grace_period_days: int
    reminder_sent: bool
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PTPReconciliationResponse(BaseModel):
    ptp_id: uuid.UUID
    previous_status: str
    current_status: str
    payments_matched: int
    total_paid: Decimal
    reconciled_at: datetime
