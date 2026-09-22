import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.account import Account
    from app.db.models.call import Call
    from app.db.models.customer import Customer


class PaymentIntent(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "payment_intents"
    __table_args__ = (
        Index("idx_payment_intent_org_status", "organization_id", "status"),
        Index("idx_payment_intent_account", "account_id"),
        Index("idx_payment_intent_ref", "reference_id"),
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

    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), default="payment_link", nullable=False)
    # upi, netbanking, card, payment_link
    status: Mapped[str] = mapped_column(String(50), default="initiated", nullable=False)
    # initiated, link_sent, pending_confirmation, confirmed, expired, cancelled

    reference_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    link_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    customer: Mapped["Customer"] = relationship("Customer")
    account: Mapped["Account"] = relationship("Account")
    call: Mapped[Optional["Call"]] = relationship("Call")
