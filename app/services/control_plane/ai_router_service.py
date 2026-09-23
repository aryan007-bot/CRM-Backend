from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Set
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ProviderUnavailableException, QuotaExceededException
from app.db.models.ai_infra import (
    AiModel,
    AiProvider,
    AiRequestMetric,
    AiRoutingRule,
    ProviderQuota,
)
from app.schemas.control_plane.ai import (
    AiLatencySummaryResponse,
    AiUsageSummaryResponse,
    ProviderQuotaResponse,
)
from app.services.control_plane.event_bus import event_bus


class AIRouter:
    """Smart AI Router enforcing health, quotas, fallback chains, and metrics without quota bypass."""

    @staticmethod
    def resolve_provider(
        db: Session,
        service_type: str,
        scope: str = "PLATFORM",
        organization_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """Resolves primary provider and models with loop-safe fallback selection."""
        # Find enabled routing rule
        rule_query = select(AiRoutingRule).where(
            AiRoutingRule.service_type == service_type,
            AiRoutingRule.enabled == True,
        )
        if organization_id:
            rule_query = rule_query.where(
                (AiRoutingRule.organization_id == organization_id) | (AiRoutingRule.scope == "PLATFORM")
            )
        rule = db.scalars(rule_query.order_by(AiRoutingRule.priority.asc())).first()

        visited_providers: Set[uuid.UUID] = set()
        fallback_used = False

        if rule:
            candidates: List[uuid.UUID] = [rule.primary_provider_id]
            if rule.fallbacks:
                for fb in rule.fallbacks:
                    if isinstance(fb, dict) and "provider_id" in fb:
                        try:
                            candidates.append(uuid.UUID(str(fb["provider_id"])))
                        except Exception:
                            pass
        else:
            # Fallback to any enabled provider for this service type
            provider_type = service_type if service_type in ("LLM", "STT", "TTS", "VAD") else "LLM"
            candidates = list(
                db.scalars(
                    select(AiProvider.id)
                    .where(AiProvider.provider_type == provider_type, AiProvider.enabled == True)
                    .order_by(AiProvider.priority.asc())
                ).all()
            )

        if not candidates:
            raise ProviderUnavailableException(f"No AI providers available for {service_type}")

        selected_provider: Optional[AiProvider] = None

        for candidate_id in candidates:
            if candidate_id in visited_providers:
                continue  # Prevent cyclic loops
            visited_providers.add(candidate_id)

            provider = db.scalar(select(AiProvider).where(AiProvider.id == candidate_id))
            if not provider or not provider.enabled or provider.status == "UNAVAILABLE":
                fallback_used = True
                continue

            # Check provider quota
            quota = db.scalar(
                select(ProviderQuota).where(
                    ProviderQuota.provider_id == provider.id,
                    ProviderQuota.metric == "REQUESTS",
                )
            )
            if quota and quota.remaining <= 0:
                fallback_used = True
                continue

            selected_provider = provider
            break

        if not selected_provider:
            raise ProviderUnavailableException("All configured AI providers are unavailable or quota-exhausted")

        # Resolve model
        model = db.scalars(
            select(AiModel).where(AiModel.provider_id == selected_provider.id, AiModel.enabled == True)
        ).first()

        return {
            "provider": selected_provider,
            "model": model,
            "fallback_used": fallback_used,
        }

    @staticmethod
    def record_request_metric(
        db: Session,
        service_type: str,
        provider_id: uuid.UUID,
        model_id: Optional[uuid.UUID] = None,
        scope: str = "PLATFORM",
        organization_id: Optional[uuid.UUID] = None,
        request_type: str = "chat",
        status: str = "SUCCESS",
        latency_ms: int = 50,
        queue_wait_ms: Optional[int] = 5,
        processing_ms: Optional[int] = 45,
        input_tokens: Optional[int] = 100,
        output_tokens: Optional[int] = 50,
        audio_duration_ms: Optional[int] = None,
        fallback_used: bool = False,
        error_code: Optional[str] = None,
    ) -> AiRequestMetric:
        metric = AiRequestMetric(
            scope=scope,
            organization_id=organization_id,
            service_type=service_type,
            provider_id=provider_id,
            model_id=model_id,
            request_type=request_type,
            status=status,
            latency_ms=latency_ms,
            queue_wait_ms=queue_wait_ms,
            processing_ms=processing_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            audio_duration_ms=audio_duration_ms,
            fallback_used=fallback_used,
            error_code=error_code,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(metric)

        # Update quota usage if configured
        quota = db.scalar(
            select(ProviderQuota).where(
                ProviderQuota.provider_id == provider_id,
                ProviderQuota.metric == "REQUESTS",
            )
        )
        if quota:
            quota.current_usage += 1
            quota.remaining = max(0, quota.configured_limit - quota.current_usage)

        db.flush()
        return metric

    @staticmethod
    def get_usage_summary(
        db: Session,
        scope: Optional[str] = None,
        organization_id: Optional[uuid.UUID] = None,
        provider_id: Optional[uuid.UUID] = None,
    ) -> AiUsageSummaryResponse:
        query = select(AiRequestMetric)
        if scope:
            query = query.where(AiRequestMetric.scope == scope)
        if organization_id:
            query = query.where(AiRequestMetric.organization_id == organization_id)
        if provider_id:
            query = query.where(AiRequestMetric.provider_id == provider_id)

        metrics = db.scalars(query).all()
        if not metrics:
            return AiUsageSummaryResponse()

        total = len(metrics)
        successes = sum(1 for m in metrics if m.status == "SUCCESS")
        failures = sum(1 for m in metrics if m.status == "FAILURE")
        fallbacks = sum(1 for m in metrics if m.fallback_used)
        tokens_in = sum(m.input_tokens or 0 for m in metrics)
        tokens_out = sum(m.output_tokens or 0 for m in metrics)
        audio_dur = sum((m.audio_duration_ms or 0) / 1000.0 for m in metrics)

        return AiUsageSummaryResponse(
            total_requests=total,
            successful_requests=successes,
            failed_requests=failures,
            fallback_requests=fallbacks,
            total_input_tokens=tokens_in,
            total_output_tokens=tokens_out,
            total_audio_duration_seconds=round(audio_dur, 2),
        )

    @staticmethod
    def get_latency_summary(
        db: Session,
        service_type: str = "LLM",
        provider_id: Optional[uuid.UUID] = None,
    ) -> AiLatencySummaryResponse:
        query = select(AiRequestMetric.latency_ms).where(
            AiRequestMetric.service_type == service_type,
            AiRequestMetric.status == "SUCCESS",
        )
        if provider_id:
            query = query.where(AiRequestMetric.provider_id == provider_id)

        latencies = sorted(db.scalars(query).all())
        if not latencies:
            return AiLatencySummaryResponse(service_type=service_type)

        n = len(latencies)
        avg = sum(latencies) / n
        p50 = latencies[int(math.floor(0.50 * (n - 1)))]
        p95 = latencies[int(math.floor(0.95 * (n - 1)))]
        p99 = latencies[int(math.floor(0.99 * (n - 1)))]

        return AiLatencySummaryResponse(
            service_type=service_type,
            average_latency_ms=round(avg, 2),
            p50_latency_ms=float(p50),
            p95_latency_ms=float(p95),
            p99_latency_ms=float(p99),
        )

    @staticmethod
    def get_quotas(db: Session, provider_id: Optional[uuid.UUID] = None) -> List[ProviderQuotaResponse]:
        query = select(ProviderQuota)
        if provider_id:
            query = query.where(ProviderQuota.provider_id == provider_id)

        quotas = db.scalars(query).all()
        results: List[ProviderQuotaResponse] = []
        for q in quotas:
            p_name = q.provider.name if q.provider else "Unknown"
            results.append(
                ProviderQuotaResponse(
                    provider_id=q.provider_id,
                    provider_name=p_name,
                    metric=q.metric,
                    configured_limit=q.configured_limit,
                    current_usage=q.current_usage,
                    remaining=q.remaining,
                    reset_at=q.reset_at,
                    source=q.source,
                )
            )
        return results
