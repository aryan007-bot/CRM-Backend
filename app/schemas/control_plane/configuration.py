import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class ConfigurationVersionResponse(BaseModel):
    id: uuid.UUID
    configuration_item_id: uuid.UUID
    version: int
    safe_value: Optional[str] = None
    change_reason: Optional[str] = None
    changed_by: Optional[uuid.UUID] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConfigurationItemUpdate(BaseModel):
    value: Any
    change_reason: Optional[str] = "Configuration updated"


class ConfigurationItemResponse(BaseModel):
    id: uuid.UUID
    scope: str
    organization_id: Optional[uuid.UUID] = None
    environment_id: Optional[uuid.UUID] = None
    key: str
    value_type: str
    is_secret: bool
    is_mutable: bool
    requires_restart: bool
    requires_deployment: bool
    description: Optional[str] = None
    source: str
    version: int
    safe_value: Optional[str] = None
    state: str
    updated_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
