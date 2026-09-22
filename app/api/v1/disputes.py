import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_role
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse, SingleResponse
from app.schemas.dispute import (
    DisputeAssignRequest,
    DisputeCreate,
    DisputeEscalateRequest,
    DisputeResolveRequest,
    DisputeResponse,
    DisputeUpdate,
)
from app.services.recovery.disputes import DisputeService

router = APIRouter(prefix="/disputes", tags=["Disputes"])


@router.post("", response_model=SingleResponse[DisputeResponse], status_code=status.HTTP_201_CREATED)
def create_dispute(
    data: DisputeCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a debtor dispute."""
    dispute = DisputeService.create_dispute(
        db=db,
        organization_id=current_user.organization_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=DisputeResponse.model_validate(dispute))


@router.get("/{dispute_id}", response_model=SingleResponse[DisputeResponse])
def get_dispute(
    dispute_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get dispute details by ID."""
    dispute = DisputeService.get_dispute(
        db=db,
        organization_id=current_user.organization_id,
        dispute_id=dispute_id,
    )
    return SingleResponse(data=DisputeResponse.model_validate(dispute))


@router.patch("/{dispute_id}", response_model=SingleResponse[DisputeResponse])
def update_dispute(
    dispute_id: uuid.UUID,
    data: DisputeUpdate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Update dispute status (e.g. resolved, rejected) and assigned user."""
    dispute = DisputeService.update_dispute(
        db=db,
        organization_id=current_user.organization_id,
        dispute_id=dispute_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=DisputeResponse.model_validate(dispute))


@router.post("/{dispute_id}/assign", response_model=SingleResponse[DisputeResponse])
def assign_dispute(
    dispute_id: uuid.UUID,
    data: DisputeAssignRequest,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Assign a dispute to an agent/manager."""
    dispute = DisputeService.assign_dispute(
        db=db,
        organization_id=current_user.organization_id,
        dispute_id=dispute_id,
        assigned_to=data.assigned_to,
        user_id=current_user.id,
    )
    return SingleResponse(data=DisputeResponse.model_validate(dispute))


@router.post("/{dispute_id}/resolve", response_model=SingleResponse[DisputeResponse])
def resolve_dispute(
    dispute_id: uuid.UUID,
    data: DisputeResolveRequest,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Mark a dispute as resolved with resolution notes."""
    dispute = DisputeService.resolve_dispute(
        db=db,
        organization_id=current_user.organization_id,
        dispute_id=dispute_id,
        resolution_notes=data.resolution_notes,
        user_id=current_user.id,
    )
    return SingleResponse(data=DisputeResponse.model_validate(dispute))


@router.post("/{dispute_id}/escalate", response_model=SingleResponse[DisputeResponse])
def escalate_dispute(
    dispute_id: uuid.UUID,
    data: Optional[DisputeEscalateRequest] = None,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Escalate a dispute to manager queue."""
    dispute = DisputeService.escalate_dispute(
        db=db,
        organization_id=current_user.organization_id,
        dispute_id=dispute_id,
        notes=data.notes if data else None,
        user_id=current_user.id,
    )
    return SingleResponse(data=DisputeResponse.model_validate(dispute))


@router.get("", response_model=PaginatedResponse[DisputeResponse])
def list_disputes(
    customer_id: Optional[uuid.UUID] = None,
    account_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    reason_category: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List disputes with filtering and pagination."""
    items, total = DisputeService.list_disputes(
        db=db,
        organization_id=current_user.organization_id,
        customer_id=customer_id,
        account_id=account_id,
        status=status_filter,
        reason_category=reason_category,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[DisputeResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )
