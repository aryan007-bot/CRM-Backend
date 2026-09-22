import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON as FallbackJSON

from app.db.base import GUID, Base, IDMixin, OrganizationMixin, TimestampMixin


class FollowUpRule(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "follow_up_rules"
    __table_args__ = (
        Index("idx_rule_org_trigger", "organization_id", "event_trigger"),
        Index("idx_rule_org_active", "organization_id", "is_active"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    event_trigger: Mapped[str] = mapped_column(String(100), nullable=False)
    # ptp_created, dispute_logged, payment_link_sent, call_unreachable, callback_scheduled
    condition_config: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(FallbackJSON, "sqlite"),
        nullable=True,
        default=dict,
    )
    action_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # send_sms, send_whatsapp, schedule_callback, update_crm, create_task
    action_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    executions: Mapped[List["AutomationExecution"]] = relationship(
        "AutomationExecution",
        back_populates="rule",
    )


class AutomationExecution(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "automation_executions"
    __table_args__ = (
        Index("idx_execution_org_status", "organization_id", "status"),
        Index("idx_execution_target", "target_entity_type", "target_entity_id"),
    )

    rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("follow_up_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    trigger_event: Mapped[str] = mapped_column(String(100), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    # customer, account, call, ptp
    target_entity_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    # pending, executed, failed

    action_output: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    rule: Mapped[Optional["FollowUpRule"]] = relationship("FollowUpRule", back_populates="executions")
    jobs: Mapped[List["FollowUpJob"]] = relationship("FollowUpJob", back_populates="execution")


class FollowUpJob(Base, IDMixin, OrganizationMixin, TimestampMixin):
    __tablename__ = "follow_up_jobs"
    __table_args__ = (
        Index("idx_job_org_status", "organization_id", "status"),
        Index("idx_job_scheduled_at", "scheduled_at"),
    )

    execution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("automation_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    # sms, whatsapp, email
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="scheduled", nullable=False)
    # scheduled, sent, delivered, failed

    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    execution: Mapped[Optional["AutomationExecution"]] = relationship("AutomationExecution", back_populates="jobs")
