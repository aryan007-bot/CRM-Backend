import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON as FallbackJSON

from app.db.base import GUID, Base, IDMixin, TimestampMixin


class ConfigurationItem(Base, IDMixin, TimestampMixin):
    __tablename__ = "configuration_items"
    __table_args__ = (
        Index("idx_config_items_scope_key", "scope", "key"),
        Index("idx_config_items_env_key", "environment_id", "key"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="PLATFORM", nullable=False)  # PLATFORM, ORGANIZATION, SERVICE
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    environment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("environments.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), default="string", nullable=False)  # string, int, bool, json
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_mutable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    requires_restart: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_deployment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    validation_schema: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )
    source: Mapped[str] = mapped_column(String(50), default="SYSTEM", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    safe_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    secret_ref: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(50), default="APPLIED", nullable=False)  # DRAFT, VALIDATING, VALID, APPLYING, APPLIED, INVALID, APPLY_FAILED
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    versions: Mapped[List["ConfigurationVersion"]] = relationship(
        "ConfigurationVersion",
        back_populates="configuration_item",
        cascade="all, delete-orphan",
    )


class ConfigurationVersion(Base, IDMixin):
    __tablename__ = "configuration_versions"
    __table_args__ = (
        Index("idx_config_versions_item_ver", "configuration_item_id", "version"),
    )

    configuration_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("configuration_items.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    safe_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    change_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    changed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    configuration_item: Mapped["ConfigurationItem"] = relationship("ConfigurationItem", back_populates="versions")
