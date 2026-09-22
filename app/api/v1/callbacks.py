import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.callback import (
    CallbackCreate,
    CallbackResponse,
    CallbackUpdate,
)
from app.schemas.common import PaginatedResponse, SingleResponse
from app.services.recovery.callbacks import CallbackService

router = APIRouter(prefix="/callbacks", tags=["Callbacks"])


@router.post("", response_model=SingleResponse[CallbackResponse], status_code=status.HTTP_201_CREATED)
def create_callback(
    data: CallbackCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Schedule a callback for a debtor."""
    callback = CallbackService.create_callback(
        db=db,
        organization_id=current_user.organization_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=CallbackResponse.model_validate(callback))


@router.get("/{callback_id}", response_model=SingleResponse[CallbackResponse])
def get_callback(
    callback_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get callback details by ID."""
    callback = CallbackService.get_callback(
        db=db,
        organization_id=current_user.organization_id,
        callback_id=callback_id,
    )
    return SingleResponse(data=CallbackResponse.model_validate(callback))


@router.patch("/{callback_id}", response_model=SingleResponse[CallbackResponse])
def update_callback(
    callback_id: uuid.UUID,
    data: CallbackUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update callback time, status, or notes."""
    callback = CallbackService.update_callback(
        db=db,
        organization_id=current_user.organization_id,
        callback_id=callback_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=CallbackResponse.model_validate(callback))


@router.post("/{callback_id}/cancel", response_model=SingleResponse[CallbackResponse])
def cancel_callback(
    callback_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a scheduled callback."""
    callback = CallbackService.cancel_callback(
        db=db,
        organization_id=current_user.organization_id,
        callback_id=callback_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=CallbackResponse.model_validate(callback))


@router.post("/{callback_id}/complete", response_model=SingleResponse[CallbackResponse])
def complete_callback(
    callback_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a scheduled callback as completed."""
    callback = CallbackService.complete_callback(
        db=db,
        organization_id=current_user.organization_id,
        callback_id=callback_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=CallbackResponse.model_validate(callback))


@router.get("", response_model=PaginatedResponse[CallbackResponse])
def list_callbacks(
    customer_id: Optional[uuid.UUID] = None,
    account_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List scheduled callbacks with pagination."""
    items, total = CallbackService.list_callbacks(
        db=db,
        organization_id=current_user.organization_id,
        customer_id=customer_id,
        account_id=account_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[CallbackResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )
