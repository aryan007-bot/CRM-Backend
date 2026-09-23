from typing import List, Optional
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.db.models.user import User
from app.schemas.control_plane.ai import (
    AiLatencySummaryResponse,
    AiUsageSummaryResponse,
    ProviderQuotaResponse,
)
from app.services.control_plane.ai_router_service import AIRouter

router = APIRouter(prefix="/ai", tags=["AI Usage & Metrics"])


@router.get("/usage", response_model=AiUsageSummaryResponse)
def get_ai_usage(
    provider_id: Optional[uuid.UUID] = None,
    scope: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = current_user.organization_id if "SUPER_ADMIN" not in current_user.roles else None
    return AIRouter.get_usage_summary(
        db=db,
        scope=scope,
        organization_id=org_id,
        provider_id=provider_id,
    )


@router.get("/latency", response_model=AiLatencySummaryResponse)
def get_ai_latency(
    service_type: str = Query("LLM"),
    provider_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return AIRouter.get_latency_summary(
        db=db,
        service_type=service_type,
        provider_id=provider_id,
    )


@router.get("/quota", response_model=List[ProviderQuotaResponse])
def get_ai_quota(
    provider_id: Optional[uuid.UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return AIRouter.get_quotas(db=db, provider_id=provider_id)
