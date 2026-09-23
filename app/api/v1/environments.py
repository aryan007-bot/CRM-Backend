import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db
from app.core.errors import NotFoundException
from app.db.models.deployment import EnvironmentRecord
from app.db.models.user import User
from app.schemas.control_plane.deployment import EnvironmentResponse
from app.services.control_plane.deployment_service import DeploymentService

router = APIRouter(prefix="/environments", tags=["Environments"])


@router.get("", response_model=List[EnvironmentResponse])
def list_environments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    DeploymentService.ensure_default_environments(db)
    envs = db.scalars(select(EnvironmentRecord)).all()
    return [EnvironmentResponse.model_validate(e) for e in envs]


@router.get("/{id}", response_model=EnvironmentResponse)
def get_environment(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    env = db.scalar(select(EnvironmentRecord).where(EnvironmentRecord.id == id))
    if not env:
        raise NotFoundException(f"Environment {id} not found", code="ENVIRONMENT_NOT_FOUND")
    return EnvironmentResponse.model_validate(env)
