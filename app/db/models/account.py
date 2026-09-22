import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.campaign import CampaignLead
    from app.db.models.creditor import Creditor
    from app.db.models.customer import Customer
    from app.db.models.organization import Organization


class Account(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("organization_id", "account_number", name="uq_account_org_accnum"),
        Index("idx_account_org_status", "organization_id", "status"),
        Index("idx_account_org_duedate", "organization_id", "due_date"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("customers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    creditor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("creditors.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    account_number: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    outstanding_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    # active, paid, disputed, closed, on_hold

    organization: Mapped["Organization"] = relationship("Organization", back_populates="accounts")
    customer: Mapped["Customer"] = relationship("Customer", back_populates="accounts", lazy="joined")
    creditor: Mapped[Optional["Creditor"]] = relationship("Creditor", back_populates="accounts", lazy="joined")
    payments: Mapped[List["AccountPayment"]] = relationship(
        "AccountPayment",
        back_populates="account",
        cascade="all, delete-orphan",
        order_by="desc(AccountPayment.payment_date)",
        lazy="selectin",
    )
    campaign_leads: Mapped[List["CampaignLead"]] = relationship("CampaignLead", back_populates="account")


class AccountPayment(Base, IDMixin):
    __tablename__ = "account_payments"

    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now(), nullable=False)
    reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="completed", nullable=False)  # completed, pending, failed
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    account: Mapped["Account"] = relationship("Account", back_populates="payments")
