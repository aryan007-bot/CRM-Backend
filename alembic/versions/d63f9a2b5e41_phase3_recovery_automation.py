"""phase3_recovery_automation

Revision ID: d63f9a2b5e41
Revises: c52e8b1a4f32
Create Date: 2026-09-22 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.db.base import GUID

# revision identifiers, used by Alembic.
revision: str = "d63f9a2b5e41"
down_revision: Union[str, Sequence[str], None] = "c52e8b1a4f32"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Alter campaigns table with Phase 3 recovery fields
    op.add_column("campaigns", sa.Column("campaign_type", sa.String(length=50), server_default="recovery", nullable=False))
    op.add_column("campaigns", sa.Column("priority", sa.Integer(), server_default="1", nullable=False))
    op.add_column("campaigns", sa.Column("creditor_id", GUID(), nullable=True))
    op.add_column("campaigns", sa.Column("ai_agent_id", GUID(), nullable=True))
    op.add_column("campaigns", sa.Column("voice_profile_id", GUID(), nullable=True))
    op.add_column("campaigns", sa.Column("language_mode", sa.String(length=50), server_default="en-IN", nullable=False))
    op.add_column("campaigns", sa.Column("start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaigns", sa.Column("end_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaigns", sa.Column("daily_attempt_limit", sa.Integer(), server_default="3", nullable=False))
    op.add_column("campaigns", sa.Column("retry_cooldown_minutes", sa.Integer(), server_default="60", nullable=False))
    op.add_column("campaigns", sa.Column("dnc_enforcement", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("campaigns", sa.Column("ai_disclosure_enabled", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("campaigns", sa.Column("recording_disclosure_enabled", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("campaigns", sa.Column("human_escalation_enabled", sa.Boolean(), server_default="true", nullable=False))
    op.add_column("campaigns", sa.Column("follow_up_enabled", sa.Boolean(), server_default="true", nullable=False))
    op.create_foreign_key("fk_campaigns_creditor_id", "campaigns", "creditors", ["creditor_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_campaigns_ai_agent_id", "campaigns", "ai_agents", ["ai_agent_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_campaigns_voice_profile_id", "campaigns", "voice_profiles", ["voice_profile_id"], ["id"], ondelete="SET NULL")

    # 2. Alter campaign_leads table
    op.add_column("campaign_leads", sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("campaign_leads", sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaign_leads", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("campaign_leads", sa.Column("last_outcome", sa.String(length=100), nullable=True))
    op.add_column("campaign_leads", sa.Column("contact_state", sa.String(length=50), server_default="uncontacted", nullable=False))
    op.create_index("idx_campaign_lead_contact_state", "campaign_leads", ["campaign_id", "contact_state"], unique=False)

    # 3. Alter customers table
    op.add_column("customers", sa.Column("is_opted_out", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("customers", sa.Column("opted_out_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("customers", sa.Column("opt_out_reason", sa.String(length=500), nullable=True))

    # 4. Create campaign_runs
    op.create_table(
        "campaign_runs",
        sa.Column("campaign_id", GUID(), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_leads", sa.Integer(), nullable=False),
        sa.Column("processed_leads", sa.Integer(), nullable=False),
        sa.Column("successful_leads", sa.Integer(), nullable=False),
        sa.Column("failed_leads", sa.Integer(), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campaign_runs_organization_id", "campaign_runs", ["organization_id"], unique=False)
    op.create_index("ix_campaign_runs_campaign_id", "campaign_runs", ["campaign_id"], unique=False)
    op.create_index("idx_campaign_run_org_status", "campaign_runs", ["organization_id", "status"], unique=False)
    op.create_index("idx_campaign_run_campaign", "campaign_runs", ["campaign_id"], unique=False)

    # 5. Create dial_queue_items
    op.create_table(
        "dial_queue_items",
        sa.Column("campaign_id", GUID(), nullable=False),
        sa.Column("campaign_run_id", GUID(), nullable=True),
        sa.Column("lead_id", GUID(), nullable=False),
        sa.Column("customer_id", GUID(), nullable=False),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("phone_number", sa.String(length=50), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reserved_by", sa.String(length=100), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_run_id"], ["campaign_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_id"], ["campaign_leads.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dial_queue_items_organization_id", "dial_queue_items", ["organization_id"], unique=False)
    op.create_index("ix_dial_queue_items_campaign_id", "dial_queue_items", ["campaign_id"], unique=False)
    op.create_index("ix_dial_queue_items_campaign_run_id", "dial_queue_items", ["campaign_run_id"], unique=False)
    op.create_index("ix_dial_queue_items_lead_id", "dial_queue_items", ["lead_id"], unique=False)
    op.create_index("ix_dial_queue_items_customer_id", "dial_queue_items", ["customer_id"], unique=False)
    op.create_index("ix_dial_queue_items_account_id", "dial_queue_items", ["account_id"], unique=False)
    op.create_index("idx_queue_org_status_prio", "dial_queue_items", ["organization_id", "status", "priority"], unique=False)
    op.create_index("idx_queue_campaign_status", "dial_queue_items", ["campaign_id", "status"], unique=False)
    op.create_index("idx_queue_scheduled_for", "dial_queue_items", ["scheduled_for"], unique=False)

    # 6. Create recovery_outcomes
    op.create_table(
        "recovery_outcomes",
        sa.Column("call_id", GUID(), nullable=True),
        sa.Column("customer_id", GUID(), nullable=False),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("campaign_id", GUID(), nullable=True),
        sa.Column("outcome_type", sa.String(length=50), nullable=False),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.String(length=50), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recovery_outcomes_organization_id", "recovery_outcomes", ["organization_id"], unique=False)
    op.create_index("ix_recovery_outcomes_call_id", "recovery_outcomes", ["call_id"], unique=False)
    op.create_index("ix_recovery_outcomes_customer_id", "recovery_outcomes", ["customer_id"], unique=False)
    op.create_index("ix_recovery_outcomes_account_id", "recovery_outcomes", ["account_id"], unique=False)
    op.create_index("ix_recovery_outcomes_campaign_id", "recovery_outcomes", ["campaign_id"], unique=False)
    op.create_index("idx_outcome_org_type", "recovery_outcomes", ["organization_id", "outcome_type"], unique=False)
    op.create_index("idx_outcome_account", "recovery_outcomes", ["account_id"], unique=False)
    op.create_index("idx_outcome_call", "recovery_outcomes", ["call_id"], unique=False)

    # 7. Create payment_intents
    op.create_table(
        "payment_intents",
        sa.Column("customer_id", GUID(), nullable=False),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("call_id", GUID(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("payment_method", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("reference_id", sa.String(length=255), nullable=True),
        sa.Column("link_url", sa.String(length=1000), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_payment_intents_organization_id", "payment_intents", ["organization_id"], unique=False)
    op.create_index("ix_payment_intents_customer_id", "payment_intents", ["customer_id"], unique=False)
    op.create_index("ix_payment_intents_account_id", "payment_intents", ["account_id"], unique=False)
    op.create_index("idx_payment_intent_org_status", "payment_intents", ["organization_id", "status"], unique=False)
    op.create_index("idx_payment_intent_account", "payment_intents", ["account_id"], unique=False)
    op.create_index("idx_payment_intent_ref", "payment_intents", ["reference_id"], unique=False)

    # 8. Create promises_to_pay
    op.create_table(
        "promises_to_pay",
        sa.Column("customer_id", GUID(), nullable=False),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("call_id", GUID(), nullable=True),
        sa.Column("outcome_id", GUID(), nullable=True),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("promised_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("grace_period_days", sa.Integer(), nullable=False),
        sa.Column("reminder_sent", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["outcome_id"], ["recovery_outcomes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_promises_to_pay_organization_id", "promises_to_pay", ["organization_id"], unique=False)
    op.create_index("ix_promises_to_pay_customer_id", "promises_to_pay", ["customer_id"], unique=False)
    op.create_index("ix_promises_to_pay_account_id", "promises_to_pay", ["account_id"], unique=False)
    op.create_index("idx_ptp_org_status", "promises_to_pay", ["organization_id", "status"], unique=False)
    op.create_index("idx_ptp_promised_date", "promises_to_pay", ["promised_date"], unique=False)
    op.create_index("idx_ptp_account", "promises_to_pay", ["account_id"], unique=False)

    # 9. Create callbacks
    op.create_table(
        "callbacks",
        sa.Column("customer_id", GUID(), nullable=False),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("call_id", GUID(), nullable=True),
        sa.Column("scheduled_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("phone_number", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("requested_by", sa.String(length=50), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_callbacks_organization_id", "callbacks", ["organization_id"], unique=False)
    op.create_index("ix_callbacks_customer_id", "callbacks", ["customer_id"], unique=False)
    op.create_index("ix_callbacks_account_id", "callbacks", ["account_id"], unique=False)
    op.create_index("idx_callback_org_status", "callbacks", ["organization_id", "status"], unique=False)
    op.create_index("idx_callback_scheduled_time", "callbacks", ["scheduled_time"], unique=False)
    op.create_index("idx_callback_account", "callbacks", ["account_id"], unique=False)

    # 10. Create disputes
    op.create_table(
        "disputes",
        sa.Column("customer_id", GUID(), nullable=False),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("call_id", GUID(), nullable=True),
        sa.Column("reason_category", sa.String(length=100), nullable=False),
        sa.Column("dispute_details", sa.Text(), nullable=False),
        sa.Column("evidence_provided", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("assigned_to", GUID(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_disputes_organization_id", "disputes", ["organization_id"], unique=False)
    op.create_index("ix_disputes_customer_id", "disputes", ["customer_id"], unique=False)
    op.create_index("ix_disputes_account_id", "disputes", ["account_id"], unique=False)
    op.create_index("idx_dispute_org_status", "disputes", ["organization_id", "status"], unique=False)
    op.create_index("idx_dispute_account", "disputes", ["account_id"], unique=False)
    op.create_index("idx_dispute_reason", "disputes", ["reason_category"], unique=False)

    # 11. Create escalations
    op.create_table(
        "escalations",
        sa.Column("customer_id", GUID(), nullable=False),
        sa.Column("account_id", GUID(), nullable=False),
        sa.Column("call_id", GUID(), nullable=True),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("priority", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("escalated_to", GUID(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["escalated_to"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_escalations_organization_id", "escalations", ["organization_id"], unique=False)
    op.create_index("ix_escalations_customer_id", "escalations", ["customer_id"], unique=False)
    op.create_index("ix_escalations_account_id", "escalations", ["account_id"], unique=False)
    op.create_index("idx_escalation_org_status", "escalations", ["organization_id", "status"], unique=False)
    op.create_index("idx_escalation_account", "escalations", ["account_id"], unique=False)
    op.create_index("idx_escalation_priority", "escalations", ["priority"], unique=False)

    # 12. Create call_analyses
    op.create_table(
        "call_analyses",
        sa.Column("call_id", GUID(), nullable=False),
        sa.Column("sentiment", sa.String(length=50), nullable=False),
        sa.Column("customer_intent", sa.String(length=100), nullable=False),
        sa.Column("key_points", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("risk_indicators", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("compliance_violations", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("suggested_next_action", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["call_id"], ["calls.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("call_id"),
    )
    op.create_index("ix_call_analyses_organization_id", "call_analyses", ["organization_id"], unique=False)
    op.create_index("idx_call_analysis_org_call", "call_analyses", ["organization_id", "call_id"], unique=False)
    op.create_index("idx_call_analysis_sentiment", "call_analyses", ["sentiment"], unique=False)

    # 13. Create follow_up_rules
    op.create_table(
        "follow_up_rules",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("event_trigger", sa.String(length=100), nullable=False),
        sa.Column("condition_config", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("action_type", sa.String(length=100), nullable=False),
        sa.Column("action_template", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("delay_minutes", sa.Integer(), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_follow_up_rules_organization_id", "follow_up_rules", ["organization_id"], unique=False)
    op.create_index("idx_rule_org_trigger", "follow_up_rules", ["organization_id", "event_trigger"], unique=False)
    op.create_index("idx_rule_org_active", "follow_up_rules", ["organization_id", "is_active"], unique=False)

    # 14. Create automation_executions
    op.create_table(
        "automation_executions",
        sa.Column("rule_id", GUID(), nullable=True),
        sa.Column("trigger_event", sa.String(length=100), nullable=False),
        sa.Column("target_entity_type", sa.String(length=50), nullable=False),
        sa.Column("target_entity_id", GUID(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("action_output", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["follow_up_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_automation_executions_organization_id", "automation_executions", ["organization_id"], unique=False)
    op.create_index("idx_execution_org_status", "automation_executions", ["organization_id", "status"], unique=False)
    op.create_index("idx_execution_target", "automation_executions", ["target_entity_type", "target_entity_id"], unique=False)

    # 15. Create follow_up_jobs
    op.create_table(
        "follow_up_jobs",
        sa.Column("execution_id", GUID(), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("payload", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["execution_id"], ["automation_executions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_follow_up_jobs_organization_id", "follow_up_jobs", ["organization_id"], unique=False)
    op.create_index("idx_job_org_status", "follow_up_jobs", ["organization_id", "status"], unique=False)
    op.create_index("idx_job_scheduled_at", "follow_up_jobs", ["scheduled_at"], unique=False)

    # 16. Create export_jobs
    op.create_table(
        "export_jobs",
        sa.Column("requested_by", GUID(), nullable=True),
        sa.Column("export_type", sa.String(length=100), nullable=False),
        sa.Column("file_format", sa.String(length=20), nullable=False),
        sa.Column("filters", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_export_jobs_organization_id", "export_jobs", ["organization_id"], unique=False)
    op.create_index("idx_export_org_status", "export_jobs", ["organization_id", "status"], unique=False)
    op.create_index("idx_export_type", "export_jobs", ["export_type"], unique=False)

    # 17. Create dnc_records
    op.create_table(
        "dnc_records",
        sa.Column("phone_number", sa.String(length=50), nullable=False),
        sa.Column("customer_id", GUID(), nullable=True),
        sa.Column("reason", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("added_by", GUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("organization_id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["added_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "phone_number", name="uq_dnc_org_phone"),
    )
    op.create_index("ix_dnc_records_organization_id", "dnc_records", ["organization_id"], unique=False)
    op.create_index("idx_dnc_org_active", "dnc_records", ["organization_id", "is_active"], unique=False)
    op.create_index("idx_dnc_phone", "dnc_records", ["phone_number"], unique=False)


def downgrade() -> None:
    op.drop_table("dnc_records")
    op.drop_table("export_jobs")
    op.drop_table("follow_up_jobs")
    op.drop_table("automation_executions")
    op.drop_table("follow_up_rules")
    op.drop_table("call_analyses")
    op.drop_table("escalations")
    op.drop_table("disputes")
    op.drop_table("callbacks")
    op.drop_table("promises_to_pay")
    op.drop_table("payment_intents")
    op.drop_table("recovery_outcomes")
    op.drop_table("dial_queue_items")
    op.drop_table("campaign_runs")

    op.drop_column("customers", "opt_out_reason")
    op.drop_column("customers", "opted_out_at")
    op.drop_column("customers", "is_opted_out")

    op.drop_index("idx_campaign_lead_contact_state", table_name="campaign_leads")
    op.drop_column("campaign_leads", "contact_state")
    op.drop_column("campaign_leads", "last_outcome")
    op.drop_column("campaign_leads", "next_attempt_at")
    op.drop_column("campaign_leads", "last_attempt_at")
    op.drop_column("campaign_leads", "attempt_count")

    op.drop_constraint("fk_campaigns_voice_profile_id", "campaigns", type_="foreignkey")
    op.drop_constraint("fk_campaigns_ai_agent_id", "campaigns", type_="foreignkey")
    op.drop_constraint("fk_campaigns_creditor_id", "campaigns", type_="foreignkey")
    op.drop_column("campaigns", "follow_up_enabled")
    op.drop_column("campaigns", "human_escalation_enabled")
    op.drop_column("campaigns", "recording_disclosure_enabled")
    op.drop_column("campaigns", "ai_disclosure_enabled")
    op.drop_column("campaigns", "dnc_enforcement")
    op.drop_column("campaigns", "retry_cooldown_minutes")
    op.drop_column("campaigns", "daily_attempt_limit")
    op.drop_column("campaigns", "end_at")
    op.drop_column("campaigns", "start_at")
    op.drop_column("campaigns", "language_mode")
    op.drop_column("campaigns", "voice_profile_id")
    op.drop_column("campaigns", "ai_agent_id")
    op.drop_column("campaigns", "creditor_id")
    op.drop_column("campaigns", "priority")
    op.drop_column("campaigns", "campaign_type")
