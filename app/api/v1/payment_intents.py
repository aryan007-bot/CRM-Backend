import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse, SingleResponse
from app.schemas.payment_intent import (
    PaymentIntentCreate,
    PaymentIntentResponse,
    PaymentIntentSendLink,
)
from app.services.recovery.payment_intents import PaymentIntentService

router = APIRouter(prefix="/payment-intents", tags=["Payment Intents"])


@router.post("", response_model=SingleResponse[PaymentIntentResponse], status_code=status.HTTP_201_CREATED)
def create_payment_intent(
    data: PaymentIntentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new payment intent with payment checkout link."""
    intent = PaymentIntentService.create_intent(
        db=db,
        organization_id=current_user.organization_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=PaymentIntentResponse.model_validate(intent))


@router.get("/{intent_id}", response_model=SingleResponse[PaymentIntentResponse])
def get_payment_intent(
    intent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get payment intent details by ID."""
    intent = PaymentIntentService.get_intent(
        db=db,
        organization_id=current_user.organization_id,
        intent_id=intent_id,
    )
    return SingleResponse(data=PaymentIntentResponse.model_validate(intent))


@router.post("/{intent_id}/send-link", response_model=SingleResponse[PaymentIntentResponse])
def send_payment_link(
    intent_id: uuid.UUID,
    data: PaymentIntentSendLink,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Send payment checkout link to debtor via SMS/WhatsApp/email."""
    intent = PaymentIntentService.send_link(
        db=db,
        organization_id=current_user.organization_id,
        intent_id=intent_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=PaymentIntentResponse.model_validate(intent))


@router.post("/{intent_id}/confirm", response_model=SingleResponse[PaymentIntentResponse])
def confirm_payment_intent(
    intent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Confirm a payment intent, deducting balance and recording payment."""
    intent = PaymentIntentService.confirm_payment(
        db=db,
        organization_id=current_user.organization_id,
        intent_id=intent_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=PaymentIntentResponse.model_validate(intent))


@router.post("/{intent_id}/verify", response_model=SingleResponse[PaymentIntentResponse])
def verify_payment_intent(
    intent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify and confirm a payment intent."""
    intent = PaymentIntentService.confirm_payment(
        db=db,
        organization_id=current_user.organization_id,
        intent_id=intent_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=PaymentIntentResponse.model_validate(intent))


@router.get("", response_model=PaginatedResponse[PaymentIntentResponse])
def list_payment_intents(
    customer_id: Optional[uuid.UUID] = None,
    account_id: Optional[uuid.UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List payment intents with filters and pagination."""
    items, total = PaymentIntentService.list_intents(
        db=db,
        organization_id=current_user.organization_id,
        customer_id=customer_id,
        account_id=account_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[PaymentIntentResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )
