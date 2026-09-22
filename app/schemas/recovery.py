import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RecoveryOutcomeCreate(BaseModel):
    call_id: Optional[uuid.UUID] = None
    customer_id: uuid.UUID
    account_id: uuid.UUID
    campaign_id: Optional[uuid.UUID] = None
    outcome_type: str = Field(..., max_length=50)
    # ptp, paid, dispute, callback_requested, escalated, refused, unreachable, wrong_party, language_barrier, not_interested
    details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    recorded_by: str = Field(default="ai", max_length=50)


class RecoveryOutcomeResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    call_id: Optional[uuid.UUID] = None
    customer_id: uuid.UUID
    account_id: uuid.UUID
    campaign_id: Optional[uuid.UUID] = None
    outcome_type: str
    details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    recorded_by: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RecoverySummary(BaseModel):
    total_calls: int
    ptp_count: int
    paid_count: int
    dispute_count: int
    callback_count: int
    escalated_count: int
    unreachable_count: int
    other_count: int
    total_ptp_amount: str
    conversion_rate: float


class DialQueueItemResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    campaign_id: uuid.UUID
    campaign_run_id: Optional[uuid.UUID] = None
    lead_id: uuid.UUID
    customer_id: uuid.UUID
    account_id: uuid.UUID
    phone_number: str
    priority: int
    status: str
    retry_count: int
    max_retries: int
    reserved_at: Optional[datetime] = None
    reserved_by: Optional[str] = None
    scheduled_for: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class DialQueueReserveRequest(BaseModel):
    worker_id: str
    campaign_id: Optional[uuid.UUID] = None
    batch_size: int = Field(default=1, ge=1, le=50)


class DialQueueReserveResponse(BaseModel):
    reserved_count: int
    items: List[DialQueueItemResponse]


class DncRecordCreate(BaseModel):
    phone_number: str = Field(..., max_length=50)
    customer_id: Optional[uuid.UUID] = None
    reason: str = Field(default="customer_request", max_length=100)
    notes: Optional[str] = None


class DncRecordResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    phone_number: str
    customer_id: Optional[uuid.UUID] = None
    reason: str
    is_active: bool
    added_by: Optional[uuid.UUID] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class RecoveryQueueActionRequest(BaseModel):
    action: str  # pause, resume, close
    item_ids: List[uuid.UUID]


class RecoveryQueueActionResponse(BaseModel):
    updated: int
