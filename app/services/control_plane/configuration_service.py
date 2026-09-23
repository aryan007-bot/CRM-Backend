import json
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ConfigurationInvalidException, NotFoundException
from app.db.models.audit import AuditLog
from app.db.models.configuration import ConfigurationItem, ConfigurationVersion
from app.services.control_plane.event_bus import event_bus


class ConfigurationService:
    """Validates, versions, and applies configuration items across environments."""

    @staticmethod
    def ensure_default_configurations(db: Session):
        defaults = [
            ("monitoring.enabled", "bool", False, "true", "Enable background monitoring worker", "SYSTEM"),
            ("rate_limit.max_per_minute", "int", False, "60", "Maximum requests per minute per IP", "SYSTEM"),
            ("ai.default_llm_provider", "string", False, "groq", "Default primary LLM provider", "SYSTEM"),
            ("ai.provider_api_key", "string", True, "******", "Global AI Provider API key secret", "SYSTEM"),
            ("worker.default_concurrency", "int", False, "5", "Default concurrency for campaign workers", "SYSTEM"),
        ]
        for key, vtype, is_sec, val, desc, src in defaults:
            existing = db.scalar(select(ConfigurationItem).where(ConfigurationItem.key == key))
            if not existing:
                item = ConfigurationItem(
                    scope="PLATFORM",
                    key=key,
                    value_type=vtype,
                    is_secret=is_sec,
                    is_mutable=True,
                    description=desc,
                    source=src,
                    version=1,
                    safe_value=val,
                    state="APPLIED",
                )
                db.add(item)
                db.flush()
                ver = ConfigurationVersion(
                    configuration_item_id=item.id,
                    version=1,
                    safe_value=val,
                    change_reason="Initial system configuration",
                )
                db.add(ver)
        db.commit()

    @staticmethod
    def validate_value(item: ConfigurationItem, raw_value: Any) -> str:
        vtype = item.value_type.lower()
        if vtype == "int":
            try:
                int_val = int(raw_value)
                return str(int_val)
            except (ValueError, TypeError):
                raise ConfigurationInvalidException(f"Value '{raw_value}' is not a valid integer")
        elif vtype == "bool":
            if isinstance(raw_value, bool):
                return "true" if raw_value else "false"
            if str(raw_value).lower() in ("true", "1", "yes"):
                return "true"
            if str(raw_value).lower() in ("false", "0", "no"):
                return "false"
            raise ConfigurationInvalidException(f"Value '{raw_value}' is not a valid boolean")
        elif vtype == "json":
            try:
                if isinstance(raw_value, (dict, list)):
                    return json.dumps(raw_value)
                json.loads(str(raw_value))
                return str(raw_value)
            except Exception:
                raise ConfigurationInvalidException(f"Value '{raw_value}' is not valid JSON")
        else:
            return str(raw_value)

    @staticmethod
    def update_configuration(
        db: Session,
        config_id: uuid.UUID,
        new_value: Any,
        change_reason: str = "Configuration updated",
        user_id: Optional[uuid.UUID] = None,
    ) -> ConfigurationItem:
        item = db.scalar(select(ConfigurationItem).where(ConfigurationItem.id == config_id))
        if not item:
            raise NotFoundException(f"Configuration item {config_id} not found", code="CONFIGURATION_NOT_FOUND")

        if not item.is_mutable:
            raise ConfigurationInvalidException(f"Configuration item '{item.key}' is immutable")

        # State transition: DRAFT -> VALIDATING
        item.state = "VALIDATING"
        validated_str = ConfigurationService.validate_value(item, new_value)
        item.state = "VALID"

        # Apply state transition
        item.state = "APPLYING"
        item.version += 1
        safe_str = "******" if item.is_secret else validated_str
        item.safe_value = safe_str
        item.state = "APPLIED"
        item.updated_by = user_id

        # Record version
        ver = ConfigurationVersion(
            configuration_item_id=item.id,
            version=item.version,
            safe_value=safe_str,
            change_reason=change_reason,
            changed_by=user_id,
        )
        db.add(ver)

        # Audit
        audit = AuditLog(
            organization_id=item.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=user_id,
            action="CONFIGURATION_CHANGED",
            entity_type="configuration_item",
            entity_id=item.id,
            metadata_json={"key": item.key, "version": item.version, "reason": change_reason},
        )
        db.add(audit)

        event_bus.emit_operational_event(
            db=db,
            event_type="configuration.changed",
            scope=item.scope,
            organization_id=item.organization_id,
            entity_type="configuration",
            entity_id=str(item.id),
            severity="INFO",
            message=f"Configuration '{item.key}' updated to version {item.version}",
            payload={"key": item.key, "version": item.version},
        )
        db.commit()
        return item
