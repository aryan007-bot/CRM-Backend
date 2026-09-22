from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class CallEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_id: uuid.UUID
    sequence: int
    event_type: str
    payload: Dict[str, Any]
    timestamp: datetime


class TranscriptMessageCreate(BaseModel):
    speaker: str = Field(..., max_length=50)  # ai, customer, agent, system
    text: str = Field(..., min_length=1)
    is_final: bool = True
    confidence: Optional[Decimal] = None


class TranscriptMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    call_id: uuid.UUID
    speaker: str
    text: str
    is_final: bool
    confidence: Optional[Decimal] = None
    start_time_offset: Optional[Decimal] = None
    end_time_offset: Optional[Decimal] = None
    timestamp: datetime


class CallCreate(BaseModel):
    customer_id: uuid.UUID
    account_id: Optional[uuid.UUID] = None
    campaign_id: Optional[uuid.UUID] = None
    agent_id: Optional[uuid.UUID] = None
    recipient_phone: str
    caller_phone: Optional[str] = "+919876543210"


class CallDispositionUpdate(BaseModel):
    disposition: str = Field(..., max_length=50)  # COMPLETED, CALLBACK, TRANSFERRED, FAILED, WRONG_NUMBER, NO_ANSWER, BUSY
    notes: Optional[str] = None


class CallTransferRequest(BaseModel):
    target_user_id: Optional[uuid.UUID] = None
    target_extension: Optional[str] = None


class CallOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    customer_id: uuid.UUID
    account_id: Optional[uuid.UUID] = None
    campaign_id: Optional[uuid.UUID] = None
    agent_id: Optional[uuid.UUID] = None
    gateway_id: Optional[uuid.UUID] = None
    assigned_user_id: Optional[uuid.UUID] = None
    caller_phone: str
    recipient_phone: str
    direction: str
    status: str
    disposition: Optional[str] = None
    duration_seconds: int
    customer_name: Optional[str] = None
    agent_name: Optional[str] = None
    account_number: Optional[str] = None
    outstanding_amount: Optional[str] = None
    start_time: Optional[datetime] = None
    answered_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime


class CallDetailOut(CallOut):
    events: List[CallEventOut] = []
    transcripts: List[TranscriptMessageOut] = []
