import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CallAnalysisCreate(BaseModel):
    sentiment: str = Field(default="neutral", max_length=50)
    customer_intent: str = Field(default="unknown", max_length=100)
    key_points: Optional[Dict[str, Any]] = None
    risk_indicators: Optional[Dict[str, Any]] = None
    compliance_violations: Optional[Dict[str, Any]] = None
    suggested_next_action: Optional[str] = None
    summary: Optional[str] = None
    confidence_score: Optional[Decimal] = None


class CallAnalysisResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    call_id: uuid.UUID
    sentiment: str
    customer_intent: str
    key_points: Optional[Dict[str, Any]] = None
    risk_indicators: Optional[Dict[str, Any]] = None
    compliance_violations: Optional[Dict[str, Any]] = None
    suggested_next_action: Optional[str] = None
    summary: Optional[str] = None
    confidence_score: Optional[Decimal] = None
    processed_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class CallAnalysisRequest(BaseModel):
    force_reprocess: bool = False
