import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.organization import Organization
    from app.db.models.user import User


class Import(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "imports"
    __table_args__ = (
        Index("idx_import_org_status", "organization_id", "status"),
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)  # csv, xlsx
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    # uploaded, processing, completed, partially_completed, failed

    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    imported_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="imports")
    creator: Mapped[Optional["User"]] = relationship("User")
    rows: Mapped[List["ImportRow"]] = relationship(
        "ImportRow",
        back_populates="import_job",
        cascade="all, delete-orphan",
    )


class ImportRow(Base, IDMixin):
    __tablename__ = "import_rows"
    __table_args__ = (
        Index("idx_import_row_job_status", "import_id", "status"),
    )

    import_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("imports.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    normalized_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    # pending, valid, invalid, duplicate, imported
    error_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    import_job: Mapped["Import"] = relationship("Import", back_populates="rows")
