import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.core.errors import NotFoundException
from app.db.models.telephony_infra import TelephonyInfrastructure
from app.db.models.user import User
from app.schemas.control_plane.telephony import (
    TelephonyInfrastructureResponse,
)

router = APIRouter(prefix="/telephony/infrastructure", tags=["Telephony Infrastructure Visibility"])


@router.get("", response_model=List[TelephonyInfrastructureResponse])
def list_telephony_infrastructure(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(TelephonyInfrastructure)
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(
            (TelephonyInfrastructure.organization_id == current_user.organization_id)
            | (TelephonyInfrastructure.scope.in_(["PLATFORM", "SERVICE"]))
        )

    nodes = db.scalars(query).all()
    return [TelephonyInfrastructureResponse.model_validate(n) for n in nodes]


@router.get("/{id}", response_model=TelephonyInfrastructureResponse)
def get_telephony_infrastructure_node(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    node = db.scalar(select(TelephonyInfrastructure).where(TelephonyInfrastructure.id == id))
    if not node:
        raise NotFoundException(f"Telephony node {id} not found", code="TELEPHONY_NODE_NOT_FOUND")
    return TelephonyInfrastructureResponse.model_validate(node)
