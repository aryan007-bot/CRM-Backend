import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConfigurationInvalidException
from app.db.models.configuration import ConfigurationItem, ConfigurationVersion
from app.services.control_plane.configuration_service import ConfigurationService


def test_configuration_ensure_defaults(db: Session):
    ConfigurationService.ensure_default_configurations(db)
    items = db.scalars(select(ConfigurationItem)).all()
    assert len(items) >= 4

    keys = [i.key for i in items]
    assert "monitoring.enabled" in keys
    assert "ai.default_llm_provider" in keys


def test_configuration_update_and_versioning(db: Session):
    ConfigurationService.ensure_default_configurations(db)
    item = db.scalar(select(ConfigurationItem).where(ConfigurationItem.key == "worker.default_concurrency"))
    assert item is not None
    assert item.version == 1

    # Update concurrency to 8
    updated = ConfigurationService.update_configuration(
        db=db,
        config_id=item.id,
        new_value=8,
        change_reason="Scale workers for surge",
    )
    assert updated.version == 2
    assert updated.safe_value == "8"
    assert updated.state == "APPLIED"

    versions = db.scalars(
        select(ConfigurationVersion).where(ConfigurationVersion.configuration_item_id == item.id)
    ).all()
    assert len(versions) == 2


def test_configuration_validation_rejection(db: Session):
    ConfigurationService.ensure_default_configurations(db)
    item = db.scalar(select(ConfigurationItem).where(ConfigurationItem.key == "worker.default_concurrency"))

    # Attempt to assign invalid non-integer string
    with pytest.raises(ConfigurationInvalidException):
        ConfigurationService.update_configuration(
            db=db,
            config_id=item.id,
            new_value="invalid-string",
        )


def test_secret_configuration_masking(db: Session):
    ConfigurationService.ensure_default_configurations(db)
    secret_item = db.scalar(select(ConfigurationItem).where(ConfigurationItem.key == "ai.provider_api_key"))
    assert secret_item is not None

    updated = ConfigurationService.update_configuration(
        db=db,
        config_id=secret_item.id,
        new_value="super-secret-api-key-12345",
        change_reason="Rotated provider key",
    )
    assert updated.safe_value == "******"
