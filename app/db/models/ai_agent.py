import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.call import Call
    from app.db.models.organization import Organization


class AiAgent(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "ai_agents"
    __table_args__ = (
        Index("idx_ai_agent_org_status", "organization_id", "status"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(50), default="en-IN", nullable=False)
    model: Mapped[str] = mapped_column(String(100), default="llama-3.3-70b-versatile", nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    disclosure: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="DRAFT", nullable=False)  # DRAFT, READY, INACTIVE
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization")
    voice_profile: Mapped[Optional["VoiceProfile"]] = relationship(
        "VoiceProfile",
        back_populates="agent",
        uselist=False,
        cascade="all, delete-orphan",
    )
    calls: Mapped[List["Call"]] = relationship("Call", back_populates="agent")


class VoiceProfile(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "voice_profiles"
    __table_args__ = (
        Index("idx_voice_profile_org", "organization_id"),
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("ai_agents.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(100), default="chatterbox", nullable=False)
    audio_path: Mapped[str] = mapped_column(String(500), nullable=False)
    sample_rate: Mapped[int] = mapped_column(default=24000, nullable=False)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Numeric(6, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="READY", nullable=False)  # PENDING, READY, FAILED

    agent: Mapped["AiAgent"] = relationship("AiAgent", back_populates="voice_profile")
