import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON as FallbackJSON

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.user import User


class ExportJob(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("idx_export_org_status", "organization_id", "status"),
        Index("idx_export_type", "export_type"),
    )

    requested_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    export_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # ptp, disputes, campaign_summary, dial_queue, call_outcomes, audits
    file_format: Mapped[str] = mapped_column(String(20), default="csv", nullable=False)
    # csv, xlsx
    filters: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )
    status: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    # queued, processing, completed, failed

    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[Optional["User"]] = relationship("User")
