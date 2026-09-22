import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.customer import Customer
    from app.db.models.user import User


class DncRecord(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "dnc_records"
    __table_args__ = (
        UniqueConstraint("organization_id", "phone_number", name="uq_dnc_org_phone"),
        Index("idx_dnc_org_active", "organization_id", "is_active"),
        Index("idx_dnc_phone", "phone_number"),
    )

    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)  # Normalized E.164
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("customers.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    reason: Mapped[str] = mapped_column(String(100), default="customer_request", nullable=False)
    # customer_request, legal, regulator, wrong_number
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    added_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    customer: Mapped[Optional["Customer"]] = relationship("Customer")
    user: Mapped[Optional["User"]] = relationship("User")
