import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class FollowUpRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    event_trigger: str = Field(..., max_length=100)
    # ptp_created, dispute_logged, payment_link_sent, call_unreachable, callback_scheduled
    condition_config: Optional[Dict[str, Any]] = None
    action_type: str = Field(..., max_length=100)
    # send_sms, send_whatsapp, schedule_callback, update_crm, create_task
    action_template: Optional[str] = None
    is_active: bool = True
    delay_minutes: int = Field(default=0, ge=0)


class FollowUpRuleUpdate(BaseModel):
    name: Optional[str] = None
    event_trigger: Optional[str] = None
    condition_config: Optional[Dict[str, Any]] = None
    action_type: Optional[str] = None
    action_template: Optional[str] = None
    is_active: Optional[bool] = None
    delay_minutes: Optional[int] = Field(default=None, ge=0)


class FollowUpRuleResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    event_trigger: str
    condition_config: Optional[Dict[str, Any]] = None
    action_type: str
    action_template: Optional[str] = None
    is_active: bool
    delay_minutes: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AutomationExecutionResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    rule_id: Optional[uuid.UUID] = None
    trigger_event: str
    target_entity_type: str
    target_entity_id: uuid.UUID
    status: str
    action_output: Optional[str] = None
    error_message: Optional[str] = None
    executed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FollowUpJobResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    execution_id: Optional[uuid.UUID] = None
    channel: str
    recipient: str
    payload: Optional[str] = None
    status: str
    scheduled_at: datetime
    sent_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class FollowUpJobUpdate(BaseModel):
    status: Optional[str] = None
    scheduled_at: Optional[datetime] = None
