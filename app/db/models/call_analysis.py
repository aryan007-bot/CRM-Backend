import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON as FallbackJSON

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin

if TYPE_CHECKING:
    from app.db.models.call import Call


class CallAnalysis(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "call_analyses"
    __table_args__ = (
        Index("idx_call_analysis_org_call", "organization_id", "call_id"),
        Index("idx_call_analysis_sentiment", "sentiment"),
    )

    call_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("calls.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    sentiment: Mapped[str] = mapped_column(String(50), default="neutral", nullable=False)
    # positive, neutral, negative, hostile
    customer_intent: Mapped[str] = mapped_column(String(100), default="unknown", nullable=False)
    # willing_to_pay, disputing, stalling, unavailable, abusive, unknown

    key_points: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )
    risk_indicators: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )
    compliance_violations: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )

    suggested_next_action: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    call: Mapped["Call"] = relationship("Call")
