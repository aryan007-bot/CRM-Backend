import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import NotFoundException
from app.db.models.configuration import ConfigurationItem, ConfigurationVersion
from app.db.models.user import User
from app.schemas.control_plane.configuration import (
    ConfigurationItemResponse,
    ConfigurationItemUpdate,
    ConfigurationVersionResponse,
)
from app.services.control_plane.configuration_service import ConfigurationService

router = APIRouter(prefix="/configuration", tags=["Configuration Center"])


@router.get("", response_model=List[ConfigurationItemResponse])
def list_configuration_items(
    scope: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ConfigurationService.ensure_default_configurations(db)

    query = select(ConfigurationItem)
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(
            (ConfigurationItem.organization_id == current_user.organization_id)
            | (ConfigurationItem.scope == "PLATFORM")
        )
    if scope:
        query = query.where(ConfigurationItem.scope == scope)

    items = db.scalars(query).all()
    return [ConfigurationItemResponse.model_validate(item) for item in items]


@router.get("/{id}", response_model=ConfigurationItemResponse)
def get_configuration_item(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.scalar(select(ConfigurationItem).where(ConfigurationItem.id == id))
    if not item:
        raise NotFoundException(f"Configuration item {id} not found", code="CONFIGURATION_NOT_FOUND")
    return ConfigurationItemResponse.model_validate(item)


@router.patch("/{id}", response_model=ConfigurationItemResponse)
def update_configuration_item(
    id: uuid.UUID,
    payload: ConfigurationItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN")),
):
    item = ConfigurationService.update_configuration(
        db=db,
        config_id=id,
        new_value=payload.value,
        change_reason=payload.change_reason or "Configuration updated",
        user_id=current_user.id,
    )
    return ConfigurationItemResponse.model_validate(item)


@router.get("/{id}/history", response_model=List[ConfigurationVersionResponse])
def get_configuration_history(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.scalar(select(ConfigurationItem).where(ConfigurationItem.id == id))
    if not item:
        raise NotFoundException(f"Configuration item {id} not found", code="CONFIGURATION_NOT_FOUND")

    versions = db.scalars(
        select(ConfigurationVersion)
        .where(ConfigurationVersion.configuration_item_id == id)
        .order_by(ConfigurationVersion.version.desc())
    ).all()

    return [ConfigurationVersionResponse.model_validate(v) for v in versions]
