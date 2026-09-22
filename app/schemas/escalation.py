import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class EscalationCreate(BaseModel):
    customer_id: uuid.UUID
    account_id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    reason: str = Field(..., max_length=100)
    # hard_objection, abusive_language, legal_threat, complex_query, customer_demanded_manager, ai_failure
    priority: str = Field(default="medium", max_length=50)  # low, medium, high, urgent
    resolution_notes: Optional[str] = None


class EscalationUpdate(BaseModel):
    status: Optional[str] = None  # open, investigating, resolved, dismissed
    escalated_to: Optional[uuid.UUID] = None
    priority: Optional[str] = None
    resolution_notes: Optional[str] = None


class EscalationAssignRequest(BaseModel):
    escalated_to: uuid.UUID


class EscalationResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=1)


class EscalationResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    account_id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    reason: str
    priority: str
    status: str
    escalated_to: Optional[uuid.UUID] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
