import uuid
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON as FallbackJSON

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.account import Account
    from app.db.models.call import Call
    from app.db.models.campaign import Campaign
    from app.db.models.customer import Customer


class RecoveryOutcome(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "recovery_outcomes"
    __table_args__ = (
        Index("idx_outcome_org_type", "organization_id", "outcome_type"),
        Index("idx_outcome_account", "account_id"),
        Index("idx_outcome_call", "call_id"),
    )

    call_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("calls.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
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
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    outcome_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # ptp, paid, dispute, callback_requested, escalated, refused, unreachable, wrong_party, language_barrier, not_interested
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(50), default="ai", nullable=False)
    # ai, agent, system

    call: Mapped[Optional["Call"]] = relationship("Call")
    customer: Mapped["Customer"] = relationship("Customer")
    account: Mapped["Account"] = relationship("Account")
    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign")
