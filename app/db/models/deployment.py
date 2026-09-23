import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, TimestampMixin


class EnvironmentRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "environments"
    __table_args__ = (
        Index("idx_environments_type_status", "environment_type", "status"),
    )

    name: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    environment_type: Mapped[str] = mapped_column(String(50), default="PRODUCTION", nullable=False)  # DEVELOPMENT, STAGING, PRODUCTION
    status: Mapped[str] = mapped_column(String(50), default="HEALTHY", nullable=False)  # HEALTHY, DEGRADED, OFFLINE, UNKNOWN
    version: Mapped[str] = mapped_column(String(50), default="1.0.0", nullable=False)
    region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    deployments: Mapped[List["DeploymentRecord"]] = relationship(
        "DeploymentRecord",
        back_populates="environment",
        cascade="all, delete-orphan",
    )


class DeploymentRecord(Base, IDMixin, TimestampMixin):
    __tablename__ = "deployments"
    __table_args__ = (
        Index("idx_deployments_env_status", "environment_id", "status"),
        Index("idx_deployments_created", "created_at"),
    )

    scope: Mapped[str] = mapped_column(String(50), default="PLATFORM", nullable=False)
    environment_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("environments.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", nullable=False)  # PENDING, RUNNING, SUCCESS, FAILED, ROLLED_BACK
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deployed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    migration_status: Mapped[str] = mapped_column(String(50), default="UP_TO_DATE", nullable=False)
    health_status: Mapped[str] = mapped_column(String(50), default="HEALTHY", nullable=False)

    environment: Mapped["EnvironmentRecord"] = relationship("EnvironmentRecord", back_populates="deployments")
