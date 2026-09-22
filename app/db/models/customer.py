import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.account import Account
    from app.db.models.organization import Organization


class Customer(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "customers"
    __table_args__ = (
        Index("idx_customer_org_name", "organization_id", "name"),
    )

    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)  # active, inactive
    is_opted_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    opted_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    opt_out_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="customers")
    phones: Mapped[List["CustomerPhone"]] = relationship(
        "CustomerPhone",
        back_populates="customer",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    accounts: Mapped[List["Account"]] = relationship("Account", back_populates="customer", cascade="all, delete-orphan")


class CustomerPhone(Base, IDMixin, TimestampMixin):
    __tablename__ = "customer_phones"

    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("customers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    phone: Mapped[str] = mapped_column(String(50), nullable=False)  # Original phone
    normalized_phone: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # Normalized +91XXXXXXXXXX
    phone_type: Mapped[str] = mapped_column(String(50), default="mobile", nullable=False)  # mobile, home, work
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    customer: Mapped["Customer"] = relationship("Customer", back_populates="phones")
