import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.analytics import (
    CampaignAnalyticsResponse,
    QueueMetricsResponse,
    RecoveryMetricsResponse,
)
from app.schemas.common import SingleResponse
from app.services.recovery.analytics import AnalyticsService

router = APIRouter(prefix="/analytics", tags=["Recovery Analytics"])


@router.get("/campaigns/{campaign_id}", response_model=SingleResponse[CampaignAnalyticsResponse])
def get_campaign_analytics(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve full performance analytics for a campaign (contact rate, PTP conversion, recovery rate)."""
    res = AnalyticsService.get_campaign_analytics(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
    )
    return SingleResponse(data=res)


@router.get("/recovery", response_model=SingleResponse[RecoveryMetricsResponse])
def get_recovery_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve organization-wide recovery metrics and outcome distributions."""
    res = AnalyticsService.get_recovery_metrics(
        db=db,
        organization_id=current_user.organization_id,
    )
    return SingleResponse(data=res)


@router.get("/queue", response_model=SingleResponse[QueueMetricsResponse])
def get_queue_metrics(
    campaign_id: Optional[uuid.UUID] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve dial queue status metrics and retry distribution."""
    res = AnalyticsService.get_queue_metrics(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
    )
    return SingleResponse(data=res)
