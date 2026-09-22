import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.account import Account
    from app.db.models.call import Call
    from app.db.models.customer import Customer
    from app.db.models.user import User


class Escalation(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "escalations"
    __table_args__ = (
        Index("idx_escalation_org_status", "organization_id", "status"),
        Index("idx_escalation_account", "account_id"),
        Index("idx_escalation_priority", "priority"),
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

    reason: Mapped[str] = mapped_column(String(100), nullable=False)
    # hard_objection, abusive_language, legal_threat, complex_query, customer_demanded_manager, ai_failure
    priority: Mapped[str] = mapped_column(String(50), default="medium", nullable=False)
    # low, medium, high, urgent
    status: Mapped[str] = mapped_column(String(50), default="open", nullable=False)
    # open, investigating, resolved, dismissed

    escalated_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer")
    account: Mapped["Account"] = relationship("Account")
    call: Mapped[Optional["Call"]] = relationship("Call")
    escalated_user: Mapped[Optional["User"]] = relationship("User")
