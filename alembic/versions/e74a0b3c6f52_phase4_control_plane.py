"""phase4_control_plane

Revision ID: e74a0b3c6f52
Revises: d63f9a2b5e41
Create Date: 2026-09-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.db.base import GUID

# revision identifiers, used by Alembic.
revision: str = "e74a0b3c6f52"
down_revision: Union[str, Sequence[str], None] = "d63f9a2b5e41"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. services
    op.create_table(
        "services",
        sa.Column("scope", sa.String(length=50), server_default="PLATFORM", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("service_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="UNKNOWN", nullable=False),
        sa.Column("version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("environment", sa.String(length=50), server_default="production", nullable=False),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("endpoint_metadata_safe", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_services_organization_id", "services", ["organization_id"], unique=False)
    op.create_index("idx_services_scope_status", "services", ["scope", "status"], unique=False)
    op.create_index("idx_services_type_env", "services", ["service_type", "environment"], unique=False)

    # 2. service_health_logs
    op.create_table(
        "service_health_logs",
        sa.Column("service_id", GUID(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("safe_message", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_service_health_logs_service_id", "service_health_logs", ["service_id"], unique=False)
    op.create_index("idx_service_health_logs_service_checked", "service_health_logs", ["service_id", "checked_at"], unique=False)

    # 3. worker_nodes
    op.create_table(
        "worker_nodes",
        sa.Column("scope", sa.String(length=50), server_default="SERVICE", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("worker_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="STARTING", nullable=False),
        sa.Column("version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("environment", sa.String(length=50), server_default="production", nullable=False),
        sa.Column("hostname", sa.String(length=255), nullable=False),
        sa.Column("concurrency", sa.Integer(), server_default="5", nullable=False),
        sa.Column("active_jobs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worker_nodes_organization_id", "worker_nodes", ["organization_id"], unique=False)
    op.create_index("idx_worker_nodes_scope_status", "worker_nodes", ["scope", "status"], unique=False)
    op.create_index("idx_worker_nodes_type", "worker_nodes", ["worker_type"], unique=False)
    op.create_index("idx_worker_nodes_heartbeat", "worker_nodes", ["last_heartbeat_at"], unique=False)

    # 4. worker_commands
    op.create_table(
        "worker_commands",
        sa.Column("worker_id", GUID(), nullable=False),
        sa.Column("command", sa.String(length=50), nullable=False),
        sa.Column("requested_by", GUID(), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="REQUESTED", nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["worker_id"], ["worker_nodes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_worker_commands_worker_id", "worker_commands", ["worker_id"], unique=False)
    op.create_index("idx_worker_cmd_worker_status", "worker_commands", ["worker_id", "status"], unique=False)
    op.create_index("idx_worker_cmd_idempotency", "worker_commands", ["idempotency_key"], unique=False)

    # 5. queues
    op.create_table(
        "queues",
        sa.Column("scope", sa.String(length=50), server_default="SERVICE", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("queue_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="HEALTHY", nullable=False),
        sa.Column("backend_reference_safe", sa.String(length=255), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queues_organization_id", "queues", ["organization_id"], unique=False)
    op.create_index("idx_queues_scope_status", "queues", ["scope", "status"], unique=False)
    op.create_index("idx_queues_type", "queues", ["queue_type"], unique=False)

    # 6. queue_metrics
    op.create_table(
        "queue_metrics",
        sa.Column("queue_id", GUID(), nullable=False),
        sa.Column("pending", sa.Integer(), server_default="0", nullable=False),
        sa.Column("running", sa.Integer(), server_default="0", nullable=False),
        sa.Column("retrying", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("dead", sa.Integer(), server_default="0", nullable=False),
        sa.Column("throughput", sa.Integer(), server_default="0", nullable=False),
        sa.Column("oldest_job_age_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("worker_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["queue_id"], ["queues.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_queue_metrics_queue_id", "queue_metrics", ["queue_id"], unique=False)
    op.create_index("idx_queue_metrics_queue_captured", "queue_metrics", ["queue_id", "captured_at"], unique=False)

    # 7. system_jobs
    op.create_table(
        "system_jobs",
        sa.Column("scope", sa.String(length=50), server_default="SERVICE", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("queue_id", GUID(), nullable=True),
        sa.Column("worker_id", GUID(), nullable=True),
        sa.Column("job_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="QUEUED", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("idempotency_key", sa.String(length=100), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=True),
        sa.Column("entity_id", GUID(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("last_error_message", sa.Text(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["queue_id"], ["queues.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["worker_id"], ["worker_nodes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_jobs_organization_id", "system_jobs", ["organization_id"], unique=False)
    op.create_index("ix_system_jobs_queue_id", "system_jobs", ["queue_id"], unique=False)
    op.create_index("ix_system_jobs_worker_id", "system_jobs", ["worker_id"], unique=False)
    op.create_index("idx_system_jobs_scope_status", "system_jobs", ["scope", "status"], unique=False)
    op.create_index("idx_system_jobs_queue_status", "system_jobs", ["queue_id", "status"], unique=False)
    op.create_index("idx_system_jobs_entity", "system_jobs", ["entity_type", "entity_id"], unique=False)
    op.create_index("idx_system_jobs_idempotency", "system_jobs", ["idempotency_key"], unique=False)

    # 8. telephony_infrastructure
    op.create_table(
        "telephony_infrastructure",
        sa.Column("scope", sa.String(length=50), server_default="SERVICE", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="ONLINE", nullable=False),
        sa.Column("registration_status", sa.String(length=50), server_default="REGISTERED", nullable=False),
        sa.Column("capacity", sa.Integer(), server_default="30", nullable=False),
        sa.Column("active_channels", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_calls", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_safe", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_telephony_infrastructure_organization_id", "telephony_infrastructure", ["organization_id"], unique=False)
    op.create_index("idx_telephony_infra_scope_status", "telephony_infrastructure", ["scope", "status"], unique=False)
    op.create_index("idx_telephony_infra_type", "telephony_infrastructure", ["type"], unique=False)

    # 9. ai_services
    op.create_table(
        "ai_services",
        sa.Column("scope", sa.String(length=50), server_default="SERVICE", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("service_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="HEALTHY", nullable=False),
        sa.Column("version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("active_jobs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("queue_depth", sa.Integer(), server_default="0", nullable=False),
        sa.Column("average_latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("p95_latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_rate", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_services_organization_id", "ai_services", ["organization_id"], unique=False)
    op.create_index("idx_ai_services_scope_status", "ai_services", ["scope", "status"], unique=False)
    op.create_index("idx_ai_services_type", "ai_services", ["service_type"], unique=False)

    # 10. ai_providers
    op.create_table(
        "ai_providers",
        sa.Column("scope", sa.String(length=50), server_default="PLATFORM", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("provider_type", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="HEALTHY", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="1", nullable=False),
        sa.Column("credential_status", sa.String(length=50), server_default="NOT_CONFIGURED", nullable=False),
        sa.Column("credential_ref", sa.String(length=255), nullable=True),
        sa.Column("health_status", sa.String(length=50), server_default="HEALTHY", nullable=False),
        sa.Column("last_health_check", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_providers_organization_id", "ai_providers", ["organization_id"], unique=False)
    op.create_index("idx_ai_providers_scope_status", "ai_providers", ["scope", "status"], unique=False)
    op.create_index("idx_ai_providers_type", "ai_providers", ["provider_type"], unique=False)

    # 11. ai_models
    op.create_table(
        "ai_models",
        sa.Column("provider_id", GUID(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("model_type", sa.String(length=50), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="HEALTHY", nullable=False),
        sa.Column("streaming_supported", sa.Boolean(), server_default="true", nullable=True),
        sa.Column("tool_support", sa.Boolean(), server_default="true", nullable=True),
        sa.Column("context_limit", sa.Integer(), nullable=True),
        sa.Column("metadata_safe", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["provider_id"], ["ai_providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_models_provider_id", "ai_models", ["provider_id"], unique=False)
    op.create_index("idx_ai_models_provider", "ai_models", ["provider_id"], unique=False)
    op.create_index("idx_ai_models_type", "ai_models", ["model_type"], unique=False)

    # 12. ai_routing_rules
    op.create_table(
        "ai_routing_rules",
        sa.Column("scope", sa.String(length=50), server_default="PLATFORM", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("service_type", sa.String(length=50), nullable=False),
        sa.Column("primary_provider_id", GUID(), nullable=False),
        sa.Column("primary_model_id", GUID(), nullable=True),
        sa.Column("fallbacks", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="1", nullable=False),
        sa.Column("conditions", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["primary_model_id"], ["ai_models.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["primary_provider_id"], ["ai_providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_routing_rules_organization_id", "ai_routing_rules", ["organization_id"], unique=False)
    op.create_index("ix_ai_routing_rules_primary_provider_id", "ai_routing_rules", ["primary_provider_id"], unique=False)
    op.create_index("idx_ai_routing_scope_service", "ai_routing_rules", ["scope", "service_type"], unique=False)

    # 13. ai_request_metrics
    op.create_table(
        "ai_request_metrics",
        sa.Column("scope", sa.String(length=50), server_default="PLATFORM", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("service_type", sa.String(length=50), nullable=False),
        sa.Column("provider_id", GUID(), nullable=False),
        sa.Column("model_id", GUID(), nullable=True),
        sa.Column("request_type", sa.String(length=50), server_default="chat", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="SUCCESS", nullable=False),
        sa.Column("latency_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("queue_wait_ms", sa.Integer(), nullable=True),
        sa.Column("processing_ms", sa.Integer(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("audio_duration_ms", sa.Integer(), nullable=True),
        sa.Column("fallback_used", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["ai_models.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["ai_providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_request_metrics_model_id", "ai_request_metrics", ["model_id"], unique=False)
    op.create_index("ix_ai_request_metrics_organization_id", "ai_request_metrics", ["organization_id"], unique=False)
    op.create_index("ix_ai_request_metrics_provider_id", "ai_request_metrics", ["provider_id"], unique=False)
    op.create_index("idx_ai_req_metrics_provider_time", "ai_request_metrics", ["provider_id", "timestamp"], unique=False)
    op.create_index("idx_ai_req_metrics_scope_time", "ai_request_metrics", ["scope", "timestamp"], unique=False)

    # 14. provider_quotas
    op.create_table(
        "provider_quotas",
        sa.Column("provider_id", GUID(), nullable=False),
        sa.Column("scope", sa.String(length=50), server_default="PLATFORM", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("metric", sa.String(length=50), server_default="REQUESTS", nullable=False),
        sa.Column("configured_limit", sa.Integer(), server_default="10000", nullable=False),
        sa.Column("current_usage", sa.Integer(), server_default="0", nullable=False),
        sa.Column("remaining", sa.Integer(), server_default="10000", nullable=False),
        sa.Column("reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=50), server_default="CONFIGURED", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["provider_id"], ["ai_providers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_provider_quotas_organization_id", "provider_quotas", ["organization_id"], unique=False)
    op.create_index("ix_provider_quotas_provider_id", "provider_quotas", ["provider_id"], unique=False)
    op.create_index("idx_provider_quotas_provider_metric", "provider_quotas", ["provider_id", "metric"], unique=False)

    # 15. incidents
    op.create_table(
        "incidents",
        sa.Column("scope", sa.String(length=50), server_default="PLATFORM", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=50), server_default="MEDIUM", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="OPEN", nullable=False),
        sa.Column("source", sa.String(length=100), server_default="SYSTEM", nullable=False),
        sa.Column("affected_service_id", GUID(), nullable=True),
        sa.Column("correlation_key", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to", GUID(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["affected_service_id"], ["services.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incidents_organization_id", "incidents", ["organization_id"], unique=False)
    op.create_index("idx_incidents_scope_status", "incidents", ["scope", "status"], unique=False)
    op.create_index("idx_incidents_severity", "incidents", ["severity"], unique=False)
    op.create_index("idx_incidents_correlation", "incidents", ["correlation_key"], unique=False)

    # 16. incident_events
    op.create_table(
        "incident_events",
        sa.Column("incident_id", GUID(), nullable=False),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=100), server_default="SYSTEM", nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("metadata_safe", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["incident_id"], ["incidents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_incident_events_incident_id", "incident_events", ["incident_id"], unique=False)
    op.create_index("idx_incident_events_incident_time", "incident_events", ["incident_id", "timestamp"], unique=False)

    # 17. alerts
    op.create_table(
        "alerts",
        sa.Column("scope", sa.String(length=50), server_default="PLATFORM", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("metric", sa.String(length=100), nullable=False),
        sa.Column("operator", sa.String(length=20), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("window_seconds", sa.Integer(), server_default="300", nullable=False),
        sa.Column("severity", sa.String(length=50), server_default="MEDIUM", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("state", sa.String(length=50), server_default="RESOLVED", nullable=False),
        sa.Column("correlation_key", sa.String(length=255), nullable=True),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alerts_organization_id", "alerts", ["organization_id"], unique=False)
    op.create_index("idx_alerts_scope_state", "alerts", ["scope", "state"], unique=False)
    op.create_index("idx_alerts_correlation", "alerts", ["correlation_key"], unique=False)

    # 18. environments
    op.create_table(
        "environments",
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("environment_type", sa.String(length=50), server_default="PRODUCTION", nullable=False),
        sa.Column("status", sa.String(length=50), server_default="HEALTHY", nullable=False),
        sa.Column("version", sa.String(length=50), server_default="1.0.0", nullable=False),
        sa.Column("region", sa.String(length=50), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_environments_name", "environments", ["name"], unique=True)
    op.create_index("idx_environments_type_status", "environments", ["environment_type", "status"], unique=False)

    # 19. deployments
    op.create_table(
        "deployments",
        sa.Column("scope", sa.String(length=50), server_default="PLATFORM", nullable=False),
        sa.Column("environment_id", GUID(), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("commit_sha", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="PENDING", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deployed_by", GUID(), nullable=True),
        sa.Column("migration_status", sa.String(length=50), server_default="UP_TO_DATE", nullable=False),
        sa.Column("health_status", sa.String(length=50), server_default="HEALTHY", nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["deployed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_deployments_environment_id", "deployments", ["environment_id"], unique=False)
    op.create_index("idx_deployments_env_status", "deployments", ["environment_id", "status"], unique=False)
    op.create_index("idx_deployments_created", "deployments", ["created_at"], unique=False)

    # 20. configuration_items
    op.create_table(
        "configuration_items",
        sa.Column("scope", sa.String(length=50), server_default="PLATFORM", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("environment_id", GUID(), nullable=True),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value_type", sa.String(length=20), server_default="string", nullable=False),
        sa.Column("is_secret", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_mutable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("requires_restart", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("requires_deployment", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("validation_schema", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("source", sa.String(length=50), server_default="SYSTEM", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("safe_value", sa.Text(), nullable=True),
        sa.Column("secret_ref", sa.String(length=255), nullable=True),
        sa.Column("state", sa.String(length=50), server_default="APPLIED", nullable=False),
        sa.Column("updated_by", GUID(), nullable=True),
        sa.Column("id", GUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["environment_id"], ["environments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_configuration_items_environment_id", "configuration_items", ["environment_id"], unique=False)
    op.create_index("ix_configuration_items_organization_id", "configuration_items", ["organization_id"], unique=False)
    op.create_index("idx_config_items_scope_key", "configuration_items", ["scope", "key"], unique=False)
    op.create_index("idx_config_items_env_key", "configuration_items", ["environment_id", "key"], unique=False)

    # 21. configuration_versions
    op.create_table(
        "configuration_versions",
        sa.Column("configuration_item_id", GUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("safe_value", sa.Text(), nullable=True),
        sa.Column("change_reason", sa.Text(), nullable=True),
        sa.Column("changed_by", GUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["configuration_item_id"], ["configuration_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_configuration_versions_configuration_item_id", "configuration_versions", ["configuration_item_id"], unique=False)
    op.create_index("idx_config_versions_item_ver", "configuration_versions", ["configuration_item_id", "version"], unique=False)

    # 22. security_events
    op.create_table(
        "security_events",
        sa.Column("scope", sa.String(length=50), server_default="PLATFORM", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("severity", sa.String(length=50), server_default="MEDIUM", nullable=False),
        sa.Column("actor_id", GUID(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("resource_type", sa.String(length=50), nullable=False),
        sa.Column("resource_id", sa.String(length=100), nullable=True),
        sa.Column("safe_details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_security_events_organization_id", "security_events", ["organization_id"], unique=False)
    op.create_index("idx_security_events_scope_time", "security_events", ["scope", "timestamp"], unique=False)
    op.create_index("idx_security_events_type", "security_events", ["event_type"], unique=False)
    op.create_index("idx_security_events_severity", "security_events", ["severity"], unique=False)

    # 23. operational_events
    op.create_table(
        "operational_events",
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("scope", sa.String(length=50), server_default="PLATFORM", nullable=False),
        sa.Column("organization_id", GUID(), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=True),
        sa.Column("severity", sa.String(length=50), server_default="INFO", nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_safe", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_operational_events_organization_id", "operational_events", ["organization_id"], unique=False)
    op.create_index("idx_op_events_scope_time", "operational_events", ["scope", "timestamp"], unique=False)
    op.create_index("idx_op_events_type", "operational_events", ["event_type"], unique=False)
    op.create_index("idx_op_events_entity", "operational_events", ["entity_type", "entity_id"], unique=False)


def downgrade() -> None:
    op.drop_table("operational_events")
    op.drop_table("security_events")
    op.drop_table("configuration_versions")
    op.drop_table("configuration_items")
    op.drop_table("deployments")
    op.drop_table("environments")
    op.drop_table("alerts")
    op.drop_table("incident_events")
    op.drop_table("incidents")
    op.drop_table("provider_quotas")
    op.drop_table("ai_request_metrics")
    op.drop_table("ai_routing_rules")
    op.drop_table("ai_models")
    op.drop_table("ai_providers")
    op.drop_table("ai_services")
    op.drop_table("telephony_infrastructure")
    op.drop_table("system_jobs")
    op.drop_table("queue_metrics")
    op.drop_table("queues")
    op.drop_table("worker_commands")
    op.drop_table("worker_nodes")
    op.drop_table("service_health_logs")
    op.drop_table("services")
