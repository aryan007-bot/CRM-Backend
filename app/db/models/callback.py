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


class Callback(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "callbacks"
    __table_args__ = (
        Index("idx_callback_org_status", "organization_id", "status"),
        Index("idx_callback_scheduled_time", "scheduled_time"),
        Index("idx_callback_account", "account_id"),
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

    scheduled_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    # pending, completed, missed, cancelled

    requested_by: Mapped[str] = mapped_column(String(50), default="customer", nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    customer: Mapped["Customer"] = relationship("Customer")
    account: Mapped["Account"] = relationship("Account")
    call: Mapped[Optional["Call"]] = relationship("Call")
