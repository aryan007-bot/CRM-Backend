import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.campaign import Campaign
    from app.db.models.dial_queue import DialQueueItem


class CampaignRun(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "campaign_runs"
    __table_args__ = (
        Index("idx_campaign_run_org_status", "organization_id", "status"),
        Index("idx_campaign_run_campaign", "campaign_id"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    run_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="scheduled", nullable=False)
    # scheduled, active, paused, stopped, completed

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    total_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    processed_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    successful_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="runs")
    queue_items: Mapped[List["DialQueueItem"]] = relationship("DialQueueItem", back_populates="campaign_run")
