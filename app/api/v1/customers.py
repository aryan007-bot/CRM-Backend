import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_role
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse, SingleResponse
from app.schemas.customer import CustomerCreate, CustomerOut, CustomerPhoneOut, CustomerUpdate
from app.services.customers import CustomerService

router = APIRouter(prefix="/customers", tags=["Customers"])


def _to_customer_out(c) -> CustomerOut:
    return CustomerOut(
        id=c.id,
        organization_id=c.organization_id,
        name=c.name,
        email=c.email,
        status=c.status,
        phones=[
            CustomerPhoneOut(
                id=p.id,
                phone=p.phone,
                normalized_phone=p.normalized_phone,
                phone_type=p.phone_type,
                is_primary=p.is_primary,
                is_verified=p.is_verified,
                created_at=p.created_at,
            )
            for p in c.phones
        ],
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=PaginatedResponse[CustomerOut])
def list_customers(
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort_by: str = "created_at",
    sort_direction: str = "desc",
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List customers with search, status filtering, and database pagination."""
    items, total = CustomerService.list_customers(
        db=db,
        organization_id=current_user.organization_id,
        search=search,
        status=status,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_direction=sort_direction,
    )
    return PaginatedResponse(
        items=[_to_customer_out(c) for c in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", response_model=SingleResponse[CustomerOut], status_code=status.HTTP_201_CREATED)
def create_customer(
    data: CustomerCreate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Create a new customer record with optional phone details."""
    customer = CustomerService.create_customer(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=data,
    )
    return SingleResponse(data=_to_customer_out(customer))


@router.get("/{customer_id}", response_model=SingleResponse[CustomerOut])
def get_customer(
    customer_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details of a single customer."""
    customer = CustomerService.get_customer(db, current_user.organization_id, customer_id)
    return SingleResponse(data=_to_customer_out(customer))


@router.patch("/{customer_id}", response_model=SingleResponse[CustomerOut])
def update_customer(
    customer_id: uuid.UUID,
    data: CustomerUpdate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Update customer details."""
    customer = CustomerService.update_customer(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        customer_id=customer_id,
        data=data,
    )
    return SingleResponse(data=_to_customer_out(customer))


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_customer(
    customer_id: uuid.UUID,
    current_user: User = Depends(require_role("ORG_ADMIN")),
    db: Session = Depends(get_db),
):
    """Delete a customer record."""
    CustomerService.delete_customer(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        customer_id=customer_id,
    )
