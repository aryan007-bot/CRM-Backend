import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse, SingleResponse
from app.schemas.ptp import (
    PTPCreate,
    PTPReconciliationResponse,
    PTPResponse,
    PTPUpdate,
)
from app.services.recovery.ptp import PTPService

router = APIRouter(prefix="/ptp", tags=["Promises To Pay"])


@router.post("", response_model=SingleResponse[PTPResponse], status_code=status.HTTP_201_CREATED)
def create_ptp(
    data: PTPCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new Promise To Pay commitment."""
    ptp = PTPService.create_ptp(
        db=db,
        organization_id=current_user.organization_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=PTPResponse.model_validate(ptp))


@router.get("/{ptp_id}", response_model=SingleResponse[PTPResponse])
def get_ptp(
    ptp_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details of a specific Promise To Pay."""
    ptp = PTPService.get_ptp(
        db=db,
        organization_id=current_user.organization_id,
        ptp_id=ptp_id,
    )
    return SingleResponse(data=PTPResponse.model_validate(ptp))


@router.post("/{ptp_id}/confirm", response_model=SingleResponse[PTPResponse])
def confirm_ptp(
    ptp_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm a Promise To Pay commitment."""
    ptp = PTPService.confirm_ptp(
        db=db,
        organization_id=current_user.organization_id,
        ptp_id=ptp_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=PTPResponse.model_validate(ptp))


@router.post("/{ptp_id}/cancel", response_model=SingleResponse[PTPResponse])
def cancel_ptp(
    ptp_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a Promise To Pay commitment."""
    ptp = PTPService.cancel_ptp(
        db=db,
        organization_id=current_user.organization_id,
        ptp_id=ptp_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=PTPResponse.model_validate(ptp))


@router.patch("/{ptp_id}", response_model=SingleResponse[PTPResponse])
def update_ptp(
    ptp_id: uuid.UUID,
    data: PTPUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update Promise To Pay status or grace period."""
    ptp = PTPService.update_ptp(
        db=db,
        organization_id=current_user.organization_id,
        ptp_id=ptp_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=PTPResponse.model_validate(ptp))


@router.post("/{ptp_id}/reconcile", response_model=SingleResponse[PTPReconciliationResponse])
def reconcile_ptp(
    ptp_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Reconcile PTP against received account payments."""
    res = PTPService.reconcile_payments(
        db=db,
        organization_id=current_user.organization_id,
        ptp_id=ptp_id,
    )
    return SingleResponse(data=res)


@router.post("/reconcile-all", response_model=SingleResponse[dict])
def reconcile_all_ptps(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Batch reconcile all active PTPs against received payments."""
    results = PTPService.reconcile_all_active(
        db=db,
        organization_id=current_user.organization_id,
    )
    return SingleResponse(data={"reconciled_count": len(results)})


@router.get("", response_model=PaginatedResponse[PTPResponse])
def list_ptps(
    customer_id: Optional[uuid.UUID] = None,
    account_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List PTP commitments with status filtering and pagination."""
    items, total = PTPService.list_ptps(
        db=db,
        organization_id=current_user.organization_id,
        customer_id=customer_id,
        account_id=account_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[PTPResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )
