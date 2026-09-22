import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_role
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse, SingleResponse
from app.schemas.creditor import CreditorCreate, CreditorOut
from app.services.creditors import CreditorService

router = APIRouter(prefix="/creditors", tags=["Creditors"])


@router.get("", response_model=PaginatedResponse[CreditorOut])
def list_creditors(
    search: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List creditors in the organization with search, filter and pagination."""
    items, total = CreditorService.list_creditors(
        db,
        current_user.organization_id,
        search=search,
        status=status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[CreditorOut.model_validate(c) for c in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", response_model=SingleResponse[CreditorOut], status_code=status.HTTP_201_CREATED)
def create_creditor(
    data: CreditorCreate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Create a new creditor."""
    creditor = CreditorService.create_creditor(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=data,
    )
    return SingleResponse(data=creditor)


@router.get("/{creditor_id}", response_model=SingleResponse[CreditorOut])
def get_creditor(
    creditor_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get single creditor details."""
    creditor = CreditorService.get_creditor(db, current_user.organization_id, creditor_id)
    return SingleResponse(data=creditor)
