from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class OperationsSnapshotResponse(BaseModel):
    active_calls: Optional[int] = 0
    queued_calls: Optional[int] = 0
    completed_calls: Optional[int] = 0
    failed_calls: Optional[int] = 0
    ai_conversations: Optional[int] = 0
    human_transfers: Optional[int] = 0
    pending_analysis: Optional[int] = 0
    pending_follow_ups: Optional[int] = 0
    queue_depth: Optional[int] = 0
    workers_available: Optional[int] = 0
    workers_total: Optional[int] = 0
    telephony_available: Optional[int] = 0
    telephony_total: Optional[int] = 0
    ai_providers_available: Optional[int] = 0
    ai_providers_total: Optional[int] = 0
    active_incidents: Optional[int] = 0
    unacknowledged_alerts: Optional[int] = 0
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
