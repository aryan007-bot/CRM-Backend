import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.call_analysis import (
    CallAnalysisRequest,
    CallAnalysisResponse,
)
from typing import Optional
from app.schemas.common import PaginatedResponse, SingleResponse
from app.services.recovery.analysis import PostCallAnalysisService

router = APIRouter(prefix="/call-analysis", tags=["Call Analysis"])
calls_analysis_router = APIRouter(prefix="/calls", tags=["Call Analysis"])


@router.get("", response_model=PaginatedResponse[CallAnalysisResponse])
def list_call_analyses(
    sentiment: Optional[str] = None,
    intent: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List post-call analyses with sentiment/intent filters and pagination."""
    items, total = PostCallAnalysisService.list_analyses(
        db=db,
        organization_id=current_user.organization_id,
        sentiment=sentiment,
        intent=intent,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[CallAnalysisResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{analysis_id}", response_model=SingleResponse[CallAnalysisResponse])
def get_call_analysis_by_id(
    analysis_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve post-call analysis by analysis ID or call ID."""
    analysis = PostCallAnalysisService.get_by_id(
        db=db,
        organization_id=current_user.organization_id,
        analysis_id=analysis_id,
    )
    return SingleResponse(data=CallAnalysisResponse.model_validate(analysis))


@calls_analysis_router.post("/{call_id}/analyze", response_model=SingleResponse[CallAnalysisResponse])
def analyze_call(
    call_id: uuid.UUID,
    data: CallAnalysisRequest = CallAnalysisRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Run post-call analysis extracting sentiment, intent, compliance checks, and summary."""
    analysis = PostCallAnalysisService.analyze_call(
        db=db,
        organization_id=current_user.organization_id,
        call_id=call_id,
        force_reprocess=data.force_reprocess,
    )
    return SingleResponse(data=CallAnalysisResponse.model_validate(analysis))


@calls_analysis_router.get("/{call_id}/analysis", response_model=SingleResponse[CallAnalysisResponse])
def get_call_analysis(
    call_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve post-call analysis for a specific call."""
    analysis = PostCallAnalysisService.get_analysis(
        db=db,
        organization_id=current_user.organization_id,
        call_id=call_id,
    )
    return SingleResponse(data=CallAnalysisResponse.model_validate(analysis))
