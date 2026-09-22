import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.account import Account
    from app.db.models.call import Call
    from app.db.models.customer import Customer
    from app.db.models.user import User


class Dispute(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "disputes"
    __table_args__ = (
        Index("idx_dispute_org_status", "organization_id", "status"),
        Index("idx_dispute_account", "account_id"),
        Index("idx_dispute_reason", "reason_category"),
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

    reason_category: Mapped[str] = mapped_column(String(100), nullable=False)
    # already_paid, wrong_amount, not_my_debt, fraud, hardship, identity_theft, other
    dispute_details: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_provided: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="logged", nullable=False)
    # logged, under_review, resolved, rejected

    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer")
    account: Mapped["Account"] = relationship("Account")
    call: Mapped[Optional["Call"]] = relationship("Call")
    assigned_user: Mapped[Optional["User"]] = relationship("User")
