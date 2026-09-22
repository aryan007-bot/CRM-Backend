import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON as FallbackJSON

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.account import Account
    from app.db.models.ai_agent import AiAgent
    from app.db.models.campaign import Campaign
    from app.db.models.customer import Customer
    from app.db.models.organization import Organization
    from app.db.models.telephony import TelephonyGateway
    from app.db.models.user import User


class Call(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "calls"
    __table_args__ = (
        Index("idx_call_org_status", "organization_id", "status"),
        Index("idx_call_customer", "customer_id"),
        Index("idx_call_account", "account_id"),
    )

    customer_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
    )
    account_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
    )
    campaign_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("campaigns.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("ai_agents.id", ondelete="SET NULL"),
        nullable=True,
    )
    gateway_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("telephony_gateways.id", ondelete="SET NULL"),
        nullable=True,
    )
    assigned_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    caller_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), default="OUTBOUND", nullable=False)  # OUTBOUND, INBOUND
    status: Mapped[str] = mapped_column(String(50), default="created", nullable=False)
    # created, connecting, ringing, connected, ai_talking, customer_talking, on_hold, transferring, human_connected, ending, ended, failed

    disposition: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # COMPLETED, CALLBACK, TRANSFERRED, FAILED, WRONG_NUMBER, NO_ANSWER, BUSY

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    answered_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    organization: Mapped["Organization"] = relationship("Organization")
    customer: Mapped["Customer"] = relationship("Customer")
    account: Mapped[Optional["Account"]] = relationship("Account")
    campaign: Mapped[Optional["Campaign"]] = relationship("Campaign")
    agent: Mapped[Optional["AiAgent"]] = relationship("AiAgent", back_populates="calls")
    gateway: Mapped[Optional["TelephonyGateway"]] = relationship("TelephonyGateway")
    assigned_user: Mapped[Optional["User"]] = relationship("User")

    events: Mapped[List["CallEvent"]] = relationship(
        "CallEvent",
        back_populates="call",
        cascade="all, delete-orphan",
        order_by="CallEvent.sequence",
    )
    transcripts: Mapped[List["TranscriptMessage"]] = relationship(
        "TranscriptMessage",
        back_populates="call",
        cascade="all, delete-orphan",
        order_by="TranscriptMessage.timestamp",
    )
    recording: Mapped[Optional["CallRecording"]] = relationship(
        "CallRecording",
        back_populates="call",
        uselist=False,
        cascade="all, delete-orphan",
    )


class CallEvent(Base, IDMixin, OrganizationMixin):
    __tablename__ = "call_events"
    __table_args__ = (
        Index("idx_call_event_seq", "call_id", "sequence"),
    )

    call_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=False,
        default=dict,
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    call: Mapped["Call"] = relationship("Call", back_populates="events")


class TranscriptMessage(Base, IDMixin, OrganizationMixin):
    __tablename__ = "transcript_messages"
    __table_args__ = (
        Index("idx_transcript_call_time", "call_id", "timestamp"),
    )

    call_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("calls.id", ondelete="CASCADE"),
        nullable=False,
    )
    speaker: Mapped[str] = mapped_column(String(50), nullable=False)  # ai, customer, agent, system
    text: Mapped[str] = mapped_column(Text, nullable=False)
    is_final: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    start_time_offset: Mapped[Optional[float]] = mapped_column(Numeric(8, 3), nullable=True)
    end_time_offset: Mapped[Optional[float]] = mapped_column(Numeric(8, 3), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    call: Mapped["Call"] = relationship("Call", back_populates="transcripts")


class CallRecording(Base, IDMixin, OrganizationMixin):
    __tablename__ = "call_recordings"
    __table_args__ = (
        Index("idx_call_rec_call", "call_id"),
    )

    call_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("calls.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(20), default="wav", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    call: Mapped["Call"] = relationship("Call", back_populates="recording")
