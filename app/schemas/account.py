import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel


class AccountPaymentCreate(BaseModel):
    amount: Decimal
    currency: str = "INR"
    payment_date: Optional[datetime] = None
    reference: Optional[str] = None
    status: str = "completed"
    notes: Optional[str] = None


class AccountPaymentOut(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    amount: Decimal
    currency: str
    payment_date: datetime
    reference: Optional[str] = None
    status: str
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class AccountCreate(BaseModel):
    customer_id: uuid.UUID
    creditor_id: Optional[uuid.UUID] = None
    account_number: str
    outstanding_amount: Decimal
    currency: str = "INR"
    due_date: Optional[date] = None
    status: str = "active"


class AccountUpdate(BaseModel):
    outstanding_amount: Optional[Decimal] = None
    due_date: Optional[date] = None
    status: Optional[str] = None
    creditor_id: Optional[uuid.UUID] = None


class AccountOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    creditor_id: Optional[uuid.UUID] = None
    account_number: str
    outstanding_amount: Decimal
    currency: str
    due_date: Optional[date] = None
    status: str
    customer_name: Optional[str] = None
    creditor_name: Optional[str] = None
    payments: List[AccountPaymentOut] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
