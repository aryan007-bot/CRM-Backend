import uuid
import pytest
from sqlalchemy.orm import Session

from app.core.errors import ProviderUnavailableException
from app.db.models.ai_infra import (
    AiModel,
    AiProvider,
    AiRoutingRule,
    ProviderQuota,
)
from app.services.control_plane.ai_router_service import AIRouter


def test_ai_router_resolves_primary(db: Session):
    provider = AiProvider(
        name="primary-groq",
        provider_type="LLM",
        scope="PLATFORM",
        priority=1,
        enabled=True,
        status="HEALTHY",
    )
    db.add(provider)
    db.flush()

    model = AiModel(
        provider_id=provider.id,
        name="llama-3.3-70b",
        model_type="LLM",
        enabled=True,
    )
    db.add(model)

    quota = ProviderQuota(
        provider_id=provider.id,
        scope="PLATFORM",
        metric="REQUESTS",
        configured_limit=100,
        current_usage=10,
        remaining=90,
    )
    db.add(quota)
    db.commit()

    resolved = AIRouter.resolve_provider(db, service_type="LLM")
    assert resolved["provider"].id == provider.id
    assert resolved["fallback_used"] is False


def test_ai_router_fallbacks_when_primary_unavailable(db: Session):
    primary = AiProvider(
        name="primary-failed",
        provider_type="LLM",
        scope="PLATFORM",
        priority=1,
        enabled=True,
        status="UNAVAILABLE",
    )
    fallback = AiProvider(
        name="secondary-healthy",
        provider_type="LLM",
        scope="PLATFORM",
        priority=2,
        enabled=True,
        status="HEALTHY",
    )
    db.add_all([primary, fallback])
    db.flush()

    rule = AiRoutingRule(
        scope="PLATFORM",
        service_type="LLM",
        primary_provider_id=primary.id,
        fallbacks=[{"provider_id": str(fallback.id)}],
        enabled=True,
        priority=1,
    )
    db.add(rule)
    db.commit()

    resolved = AIRouter.resolve_provider(db, service_type="LLM")
    assert resolved["provider"].id == fallback.id
    assert resolved["fallback_used"] is True


def test_ai_router_record_request_metric_and_summaries(db: Session):
    provider = AiProvider(
        name="metric-provider",
        provider_type="LLM",
        scope="PLATFORM",
        priority=1,
        enabled=True,
        status="HEALTHY",
    )
    db.add(provider)
    db.flush()

    # Record two requests
    AIRouter.record_request_metric(
        db=db,
        service_type="LLM",
        provider_id=provider.id,
        status="SUCCESS",
        latency_ms=60,
        input_tokens=100,
        output_tokens=40,
    )
    AIRouter.record_request_metric(
        db=db,
        service_type="LLM",
        provider_id=provider.id,
        status="SUCCESS",
        latency_ms=120,
        input_tokens=150,
        output_tokens=60,
    )
    db.commit()

    usage = AIRouter.get_usage_summary(db, provider_id=provider.id)
    assert usage.total_requests == 2
    assert usage.successful_requests == 2
    assert usage.total_input_tokens == 250
    assert usage.total_output_tokens == 100

    latency = AIRouter.get_latency_summary(db, service_type="LLM", provider_id=provider.id)
    assert latency.average_latency_ms == 90.0
    assert latency.p50_latency_ms >= 60.0
