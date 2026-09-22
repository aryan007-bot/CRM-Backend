import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_role
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse, SingleResponse
from app.schemas.escalation import (
    EscalationAssignRequest,
    EscalationCreate,
    EscalationResolveRequest,
    EscalationResponse,
    EscalationUpdate,
)
from app.services.recovery.escalations import EscalationService

router = APIRouter(prefix="/escalations", tags=["Escalations"])


@router.post("", response_model=SingleResponse[EscalationResponse], status_code=status.HTTP_201_CREATED)
def create_escalation(
    data: EscalationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log an escalation for manager intervention."""
    escalation = EscalationService.create_escalation(
        db=db,
        organization_id=current_user.organization_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=EscalationResponse.model_validate(escalation))


@router.get("/{escalation_id}", response_model=SingleResponse[EscalationResponse])
def get_escalation(
    escalation_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get escalation details by ID."""
    escalation = EscalationService.get_escalation(
        db=db,
        organization_id=current_user.organization_id,
        escalation_id=escalation_id,
    )
    return SingleResponse(data=EscalationResponse.model_validate(escalation))


@router.patch("/{escalation_id}", response_model=SingleResponse[EscalationResponse])
def update_escalation(
    escalation_id: uuid.UUID,
    data: EscalationUpdate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Update escalation status, priority, or assignee."""
    escalation = EscalationService.update_escalation(
        db=db,
        organization_id=current_user.organization_id,
        escalation_id=escalation_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=EscalationResponse.model_validate(escalation))


@router.post("/{escalation_id}/assign", response_model=SingleResponse[EscalationResponse])
def assign_escalation(
    escalation_id: uuid.UUID,
    data: EscalationAssignRequest,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Assign an escalation to an agent/manager."""
    escalation = EscalationService.assign_escalation(
        db=db,
        organization_id=current_user.organization_id,
        escalation_id=escalation_id,
        escalated_to=data.escalated_to,
        user_id=current_user.id,
    )
    return SingleResponse(data=EscalationResponse.model_validate(escalation))


@router.post("/{escalation_id}/resolve", response_model=SingleResponse[EscalationResponse])
def resolve_escalation(
    escalation_id: uuid.UUID,
    data: EscalationResolveRequest,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Mark an escalation as resolved with notes."""
    escalation = EscalationService.resolve_escalation(
        db=db,
        organization_id=current_user.organization_id,
        escalation_id=escalation_id,
        resolution_notes=data.resolution_notes,
        user_id=current_user.id,
    )
    return SingleResponse(data=EscalationResponse.model_validate(escalation))


@router.post("/{escalation_id}/cancel", response_model=SingleResponse[EscalationResponse])
def cancel_escalation(
    escalation_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Dismiss or cancel an escalation."""
    escalation = EscalationService.cancel_escalation(
        db=db,
        organization_id=current_user.organization_id,
        escalation_id=escalation_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=EscalationResponse.model_validate(escalation))


@router.get("", response_model=PaginatedResponse[EscalationResponse])
def list_escalations(
    customer_id: Optional[uuid.UUID] = None,
    account_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List escalations with filtering and pagination."""
    items, total = EscalationService.list_escalations(
        db=db,
        organization_id=current_user.organization_id,
        customer_id=customer_id,
        account_id=account_id,
        status=status_filter,
        priority=priority,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[EscalationResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )
