import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.account import Account
    from app.db.models.campaign import Campaign, CampaignLead
    from app.db.models.campaign_run import CampaignRun
    from app.db.models.customer import Customer


class DialQueueItem(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "dial_queue_items"
    __table_args__ = (
        Index("idx_queue_org_status_prio", "organization_id", "status", "priority"),
        Index("idx_queue_campaign_status", "campaign_id", "status"),
        Index("idx_queue_scheduled_for", "scheduled_for"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    campaign_run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("campaign_runs.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("campaign_leads.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
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
    phone_number: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    # pending, reserved, dialing, completed, failed, expired

    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    reserved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reserved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    scheduled_for: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    campaign: Mapped["Campaign"] = relationship("Campaign")
    campaign_run: Mapped[Optional["CampaignRun"]] = relationship("CampaignRun", back_populates="queue_items")
    lead: Mapped["CampaignLead"] = relationship("CampaignLead")
    customer: Mapped["Customer"] = relationship("Customer")
    account: Mapped["Account"] = relationship("Account")
