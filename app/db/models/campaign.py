import uuid
from datetime import datetime, time
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.account import Account
    from app.db.models.ai_agent import AiAgent, VoiceProfile
    from app.db.models.campaign_run import CampaignRun
    from app.db.models.creditor import Creditor
    from app.db.models.organization import Organization
    from app.db.models.user import User


class Campaign(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "campaigns"
    __table_args__ = (
        Index("idx_campaign_org_status", "organization_id", "status"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="draft", nullable=False)
    # draft, ready, running, paused, completed, archived

    campaign_type: Mapped[str] = mapped_column(String(50), default="recovery", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    creditor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("creditors.id", ondelete="SET NULL"),
        nullable=True,
    )
    ai_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("ai_agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    voice_profile_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("voice_profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    language_mode: Mapped[str] = mapped_column(String(50), default="en-IN", nullable=False)

    timezone: Mapped[str] = mapped_column(String(100), default="Asia/Kolkata", nullable=False)
    calling_start_time: Mapped[time] = mapped_column(Time, default=time(9, 0), nullable=False)
    calling_end_time: Mapped[time] = mapped_column(Time, default=time(18, 0), nullable=False)
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    daily_attempt_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    retry_delay_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    retry_cooldown_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    concurrency_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)

    dnc_enforcement: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ai_disclosure_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    recording_disclosure_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    human_escalation_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    follow_up_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="campaigns")
    creator: Mapped[Optional["User"]] = relationship("User")
    creditor: Mapped[Optional["Creditor"]] = relationship("Creditor")
    ai_agent: Mapped[Optional["AiAgent"]] = relationship("AiAgent")
    voice_profile: Mapped[Optional["VoiceProfile"]] = relationship("VoiceProfile")
    leads: Mapped[List["CampaignLead"]] = relationship(
        "CampaignLead",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )
    runs: Mapped[List["CampaignRun"]] = relationship(
        "CampaignRun",
        back_populates="campaign",
        cascade="all, delete-orphan",
    )


class CampaignLead(Base, IDMixin, TimestampMixin):
    __tablename__ = "campaign_leads"
    __table_args__ = (
        UniqueConstraint("campaign_id", "account_id", name="uq_campaign_lead_acc"),
        Index("idx_campaign_lead_status", "campaign_id", "status"),
        Index("idx_campaign_lead_contact_state", "campaign_id", "contact_state"),
    )

    campaign_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    # pending, queued, processing, completed, retry, skipped, failed
    priority: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_outcome: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    contact_state: Mapped[str] = mapped_column(String(50), default="uncontacted", nullable=False)
    # uncontacted, contacted, promised, disputed, unreachable, dnc, resolved

    campaign: Mapped["Campaign"] = relationship("Campaign", back_populates="leads")
    account: Mapped["Account"] = relationship("Account", back_populates="campaign_leads", lazy="joined")
