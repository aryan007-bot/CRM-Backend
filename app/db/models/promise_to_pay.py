import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.account import Account
    from app.db.models.call import Call
    from app.db.models.customer import Customer
    from app.db.models.recovery_outcome import RecoveryOutcome


class PromiseToPay(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "promises_to_pay"
    __table_args__ = (
        Index("idx_ptp_org_status", "organization_id", "status"),
        Index("idx_ptp_promised_date", "promised_date"),
        Index("idx_ptp_account", "account_id"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("customers.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    call_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("calls.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    outcome_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("recovery_outcomes.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    promised_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    # active, kept, broken, cancelled

    grace_period_days: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    customer: Mapped["Customer"] = relationship("Customer")
    account: Mapped["Account"] = relationship("Account")
    call: Mapped[Optional["Call"]] = relationship("Call")
    outcome: Mapped[Optional["RecoveryOutcome"]] = relationship("RecoveryOutcome")
