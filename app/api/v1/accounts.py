import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_role
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.account import (
    AccountCreate,
    AccountOut,
    AccountPaymentCreate,
    AccountPaymentOut,
    AccountUpdate,
)
from app.schemas.common import PaginatedResponse, SingleResponse
from app.services.accounts import AccountService

router = APIRouter(prefix="/accounts", tags=["Accounts"])


def _to_account_out(acc) -> AccountOut:
    return AccountOut(
        id=acc.id,
        organization_id=acc.organization_id,
        customer_id=acc.customer_id,
        creditor_id=acc.creditor_id,
        account_number=acc.account_number,
        outstanding_amount=acc.outstanding_amount,
        currency=acc.currency,
        due_date=acc.due_date,
        status=acc.status,
        customer_name=acc.customer.name if acc.customer else None,
        creditor_name=acc.creditor.name if acc.creditor else None,
        payments=[
            AccountPaymentOut(
                id=p.id,
                account_id=p.account_id,
                amount=p.amount,
                currency=p.currency,
                payment_date=p.payment_date,
                reference=p.reference,
                status=p.status,
                notes=p.notes,
                created_at=p.created_at,
            )
            for p in acc.payments
        ],
        created_at=acc.created_at,
        updated_at=acc.updated_at,
    )


@router.get("", response_model=PaginatedResponse[AccountOut])
def list_accounts(
    search: Optional[str] = None,
    status: Optional[str] = None,
    creditor_id: Optional[uuid.UUID] = None,
    customer_id: Optional[uuid.UUID] = None,
    due_date_from: Optional[date] = None,
    due_date_to: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: str = "created_at",
    sort_direction: str = "desc",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List accounts with filters, search, and pagination."""
    items, total = AccountService.list_accounts(
        db=db,
        organization_id=current_user.organization_id,
        search=search,
        status=status,
        creditor_id=creditor_id,
        customer_id=customer_id,
        due_date_from=due_date_from,
        due_date_to=due_date_to,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )
    return PaginatedResponse(
        items=[_to_account_out(a) for a in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", response_model=SingleResponse[AccountOut], status_code=status.HTTP_201_CREATED)
def create_account(
    data: AccountCreate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Create a new account record."""
    account = AccountService.create_account(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=data,
    )
    return SingleResponse(data=_to_account_out(account))


@router.get("/{account_id}", response_model=SingleResponse[AccountOut])
def get_account(
    account_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details of a single account including payment history."""
    account = AccountService.get_account(db, current_user.organization_id, account_id)
    return SingleResponse(data=_to_account_out(account))


@router.patch("/{account_id}", response_model=SingleResponse[AccountOut])
def update_account(
    account_id: uuid.UUID,
    data: AccountUpdate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Update account details."""
    account = AccountService.update_account(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        account_id=account_id,
        data=data,
    )
    return SingleResponse(data=_to_account_out(account))


@router.post("/{account_id}/payments", response_model=SingleResponse[AccountPaymentOut], status_code=status.HTTP_201_CREATED)
def add_payment(
    account_id: uuid.UUID,
    data: AccountPaymentCreate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Record historical payment on account."""
    payment = AccountService.add_payment(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        account_id=account_id,
        data=data,
    )
    return SingleResponse(data=AccountPaymentOut.model_validate(payment))
