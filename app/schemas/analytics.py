import uuid
from decimal import Decimal
from typing import Dict, List, Optional
from pydantic import BaseModel


class CampaignAnalyticsResponse(BaseModel):
    campaign_id: uuid.UUID
    campaign_name: str
    total_leads: int
    attempted_leads: int
    contacted_leads: int
    ptp_count: int
    ptp_amount: Decimal
    paid_count: int
    paid_amount: Decimal
    dispute_count: int
    callback_count: int
    escalated_count: int
    contact_rate: float
    ptp_conversion_rate: float
    recovery_rate: float


class RecoveryMetricsResponse(BaseModel):
    total_outcomes: int
    ptp_count: int
    paid_count: int
    dispute_count: int
    callback_count: int
    escalated_count: int
    unreachable_count: int
    refused_count: int
    other_count: int
    total_outstanding: Decimal
    total_ptp_amount: Decimal
    total_collected_amount: Decimal
    dispute_rate: float
    escalation_rate: float
    ptp_kept_rate: float


class QueueMetricsResponse(BaseModel):
    total_queued: int
    pending_count: int
    reserved_count: int
    dialing_count: int
    completed_count: int
    failed_count: int
    expired_count: int
    retry_distribution: Dict[int, int]
