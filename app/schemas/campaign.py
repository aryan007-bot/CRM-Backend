import uuid
from datetime import datetime, time
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    campaign_type: str = Field(default="recovery", max_length=50)
    priority: int = Field(default=1, ge=1, le=10)
    creditor_id: Optional[uuid.UUID] = None
    ai_agent_id: Optional[uuid.UUID] = None
    voice_profile_id: Optional[uuid.UUID] = None
    language_mode: str = Field(default="en-IN", max_length=50)

    timezone: str = "Asia/Kolkata"
    calling_start_time: time = time(9, 0)
    calling_end_time: time = time(18, 0)
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    max_attempts: int = Field(default=3, ge=1, le=10)
    daily_attempt_limit: int = Field(default=3, ge=1, le=10)
    retry_delay_minutes: int = Field(default=60, ge=1)
    retry_cooldown_minutes: int = Field(default=60, ge=1)
    concurrency_limit: int = Field(default=5, ge=1, le=100)

    dnc_enforcement: bool = True
    ai_disclosure_enabled: bool = True
    recording_disclosure_enabled: bool = True
    human_escalation_enabled: bool = True
    follow_up_enabled: bool = True


class CampaignUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    campaign_type: Optional[str] = None
    priority: Optional[int] = Field(default=None, ge=1, le=10)
    creditor_id: Optional[uuid.UUID] = None
    ai_agent_id: Optional[uuid.UUID] = None
    voice_profile_id: Optional[uuid.UUID] = None
    language_mode: Optional[str] = None

    status: Optional[str] = None  # draft, ready, running, paused, completed, archived
    timezone: Optional[str] = None
    calling_start_time: Optional[time] = None
    calling_end_time: Optional[time] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    max_attempts: Optional[int] = Field(default=None, ge=1, le=10)
    daily_attempt_limit: Optional[int] = Field(default=None, ge=1, le=10)
    retry_delay_minutes: Optional[int] = Field(default=None, ge=1)
    retry_cooldown_minutes: Optional[int] = Field(default=None, ge=1)
    concurrency_limit: Optional[int] = Field(default=None, ge=1, le=100)

    dnc_enforcement: Optional[bool] = None
    ai_disclosure_enabled: Optional[bool] = None
    recording_disclosure_enabled: Optional[bool] = None
    human_escalation_enabled: Optional[bool] = None
    follow_up_enabled: Optional[bool] = None


class CampaignOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    description: Optional[str] = None
    status: str
    campaign_type: str = "recovery"
    priority: int = 1
    creditor_id: Optional[uuid.UUID] = None
    ai_agent_id: Optional[uuid.UUID] = None
    voice_profile_id: Optional[uuid.UUID] = None
    language_mode: str = "en-IN"

    timezone: str
    calling_start_time: time
    calling_end_time: time
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None

    max_attempts: int
    daily_attempt_limit: int = 3
    retry_delay_minutes: int
    retry_cooldown_minutes: int = 60
    concurrency_limit: int

    dnc_enforcement: bool = True
    ai_disclosure_enabled: bool = True
    recording_disclosure_enabled: bool = True
    human_escalation_enabled: bool = True
    follow_up_enabled: bool = True

    total_leads: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AddLeadsRequest(BaseModel):
    account_ids: List[uuid.UUID]
    priority: int = 1


class CampaignLeadOut(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    account_id: uuid.UUID
    account_number: Optional[str] = None
    customer_name: Optional[str] = None
    outstanding_amount: Optional[Decimal] = None
    status: str
    priority: int
    attempt_count: int = 0
    last_attempt_at: Optional[datetime] = None
    next_attempt_at: Optional[datetime] = None
    last_outcome: Optional[str] = None
    contact_state: str = "uncontacted"
    created_at: datetime

    class Config:
        from_attributes = True


class CampaignLeadBulkAction(BaseModel):
    lead_ids: List[uuid.UUID]
    action: str  # retry, skip, reset_attempts, change_priority
    priority: Optional[int] = Field(default=None, ge=1, le=10)


class CampaignValidationIssue(BaseModel):
    severity: str  # error, warning
    code: str
    message: str


class CampaignValidationResponse(BaseModel):
    valid: bool
    total_leads: int
    eligible_leads: int
    issues: List[CampaignValidationIssue]


class CampaignRunResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    campaign_id: uuid.UUID
    run_number: int
    status: str
    started_at: Optional[datetime] = None
    paused_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_leads: int = 0
    processed_leads: int = 0
    successful_leads: int = 0
    failed_leads: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class CampaignMetricsOut(BaseModel):
    campaign_id: uuid.UUID
    total_leads: int = 0
    pending: int = 0
    attempted: int = 0
    connected: int = 0
    conversations: int = 0
    promised: int = 0
    paid: int = 0
    disputed: int = 0
    callbacks: int = 0
    escalations: int = 0
    follow_ups_pending: int = 0


class OutcomeCount(BaseModel):
    outcome: str
    count: int


class IntentCount(BaseModel):
    intent: str
    count: int


class DistributionSet(BaseModel):
    recovery_outcomes: List[OutcomeCount]
    call_outcomes: List[OutcomeCount]
    payment_intents: List[IntentCount]


class CampaignActivityItem(BaseModel):
    id: uuid.UUID
    campaign_id: uuid.UUID
    action: str
    actor: Optional[str] = None
    detail: Optional[str] = None
    created_at: datetime


class CampaignLeadFilterInput(BaseModel):
    creditor_id: Optional[uuid.UUID] = None
    min_outstanding: Optional[Decimal] = None
    max_outstanding: Optional[Decimal] = None
    due_date_from: Optional[datetime] = None
    due_date_to: Optional[datetime] = None
    min_days_overdue: Optional[int] = None
    max_days_overdue: Optional[int] = None
    account_status: Optional[str] = None
    previous_outcome: Optional[str] = None
    ptp_status: Optional[str] = None
    callback_status: Optional[str] = None
    payment_status: Optional[str] = None


class LeadFilterStats(BaseModel):
    total: int = 0
    eligible: int = 0
    blocked: int = 0
    warnings: int = 0
    errors: int = 0


class LeadPreviewResult(BaseModel):
    stats: LeadFilterStats
    account_ids: List[uuid.UUID]


class CampaignLeadUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[int] = None


class CampaignLeadBulk(BaseModel):
    action: str  # add_to_queue | remove | pause | resume
    lead_ids: List[uuid.UUID]
