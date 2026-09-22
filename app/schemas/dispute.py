import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class DisputeCreate(BaseModel):
    customer_id: uuid.UUID
    account_id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    reason_category: str = Field(..., max_length=100)
    # already_paid, wrong_amount, not_my_debt, fraud, hardship, identity_theft, other
    dispute_details: str = Field(..., min_length=1)
    evidence_provided: bool = False


class DisputeUpdate(BaseModel):
    status: Optional[str] = None  # logged, under_review, resolved, rejected
    assigned_to: Optional[uuid.UUID] = None
    resolution_notes: Optional[str] = None


class DisputeAssignRequest(BaseModel):
    assigned_to: uuid.UUID


class DisputeResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=1)


class DisputeEscalateRequest(BaseModel):
    notes: Optional[str] = None


class DisputeResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    account_id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    reason_category: str
    dispute_details: str
    evidence_provided: bool
    status: str
    assigned_to: Optional[uuid.UUID] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
