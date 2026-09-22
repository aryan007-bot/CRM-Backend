"""phase2_telephony_and_ai

Revision ID: c52e8b1a4f32
Revises: b41c9a7f2e10
Create Date: 2026-09-22 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.db.base import GUID

# revision identifiers, used by Alembic.
revision: str = "c52e8b1a4f32"
down_revision: Union[str, Sequence[str], None] = "b41c9a7f2e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. ai_agents
    op.create_table(
        "ai_agents",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=50), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("disclosure", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_agents_organization_id", "ai_agents", ["organization_id"], unique=False)
    op.create_index("idx_ai_agent_org_status", "ai_agents", ["organization_id", "status"], unique=False)

    # 2. voice_profiles
    op.create_table(
        "voice_profiles",
        sa.Column("agent_id", GUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("audio_path", sa.String(length=500), nullable=False),
        sa.Column("sample_rate", sa.Integer(), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_id"),
    )
    op.create_index("ix_voice_profiles_organization_id", "voice_profiles", ["organization_id"], unique=False)
    op.create_index("idx_voice_profile_org", "voice_profiles", ["organization_id"], unique=False)

    # 3. telephony_gateways
    op.create_table(
        "telephony_gateways",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("gateway_type", sa.String(length=50), nullable=False),
        sa.Column("host", sa.String(length=255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("signal_strength", sa.Integer(), nullable=True),
        sa.Column("network_operator", sa.String(length=100), nullable=True),
        sa.Column("active_channels", sa.Integer(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_telephony_gateways_organization_id", "telephony_gateways", ["organization_id"], unique=False)
    op.create_index("idx_telephony_gw_org_status", "telephony_gateways", ["organization_id", "status"], unique=False)

    # 4. ai_service_status
    op.create_table(
        "ai_service_status",
        sa.Column("service_type", sa.String(length=50), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ai_service_type", "ai_service_status", ["service_type"], unique=False)

    # 5. calls
    op.create_table(
        "calls",
        sa.Column("customer_id", GUID(), nullable=False),
        sa.Column("account_id", GUID(), nullable=True),
        sa.Column("campaign_id", GUID(), nullable=True),
        sa.Column("agent_id", GUID(), nullable=True),
        sa.Column("gateway_id", GUID(), nullable=True),
        sa.Column("assigned_user_id", GUID(), nullable=True),
        sa.Column("caller_phone", sa.String(length=50), nullable=False),
        sa.Column("recipient_phone", sa.String(length=50), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("disposition", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("answered_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["agent_id"], ["ai_agents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gateway_id"], ["telephony_gateways.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_calls_organization_id", "calls", ["organization_id"], unique=False)
    op.create_index("idx_call_org_status", "calls", ["organization_id", "status"], unique=False)
    op.create_index("idx_call_customer", "calls", ["customer_id"], unique=False)
    op.create_index("idx_call_account", "calls", ["account_id"], unique=False)

    # 6. call_events
    op.create_table(
        "call_events",
        sa.Column("call_id", GUID(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON().with_variant(postgresql.JSON(), "postgresql"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_call_events_organization_id", "call_events", ["organization_id"], unique=False)
    op.create_index("idx_call_event_seq", "call_events", ["call_id", "sequence"], unique=False)

    # 7. transcript_messages
    op.create_table(
        "transcript_messages",
        sa.Column("call_id", GUID(), nullable=False),
        sa.Column("speaker", sa.String(length=50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column("start_time_offset", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("end_time_offset", sa.Numeric(precision=8, scale=3), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transcript_messages_organization_id", "transcript_messages", ["organization_id"], unique=False)
    op.create_index("idx_transcript_call_time", "transcript_messages", ["call_id", "timestamp"], unique=False)

    # 8. call_recordings
    op.create_table(
        "call_recordings",
        sa.Column("call_id", GUID(), nullable=False),
        sa.Column("storage_path", sa.String(length=500), nullable=False),
        sa.Column("duration_seconds", sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_id"),
    )
    op.create_index("ix_call_recordings_organization_id", "call_recordings", ["organization_id"], unique=False)
    op.create_index("idx_call_rec_call", "call_recordings", ["call_id"], unique=False)


def downgrade() -> None:
    op.drop_table("call_recordings")
    op.drop_table("transcript_messages")
    op.drop_table("call_events")
    op.drop_table("calls")
    op.drop_table("ai_service_status")
    op.drop_table("telephony_gateways")
    op.drop_table("voice_profiles")
    op.drop_table("ai_agents")
