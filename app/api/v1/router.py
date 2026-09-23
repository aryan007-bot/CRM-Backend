from fastapi import APIRouter

# Phase 1 Routers
from app.api.v1.accounts import router as accounts_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.auth import router as auth_router
from app.api.v1.campaigns import router as campaigns_router
from app.api.v1.creditors import router as creditors_router
from app.api.v1.customers import router as customers_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.imports import router as imports_router
from app.api.v1.profile import router as profile_router

# Phase 2 Routers
from app.api.v1.ai_agents import router as ai_agents_router
from app.api.v1.live_calls import router as live_calls_router
from app.api.v1.telephony import router as telephony_router
from app.api.v1.ws import router as ws_router

# Phase 3 Routers
from app.api.v1.automation import router as automation_router, rules_alias_router
from app.api.v1.call_analysis import router as call_analysis_router, calls_analysis_router
from app.api.v1.callbacks import router as callbacks_router
from app.api.v1.disputes import router as disputes_router
from app.api.v1.escalations import router as escalations_router
from app.api.v1.exports import router as exports_router
from app.api.v1.follow_ups import router as follow_ups_router
from app.api.v1.payment_intents import router as payment_intents_router
from app.api.v1.ptp import router as ptp_router
from app.api.v1.recovery import router as recovery_router

# Phase 4 Routers
from app.api.v1.ai_infrastructure import router as ai_infra_router, voice_router as ai_voice_infra_router
from app.api.v1.ai_models import router as ai_models_router
from app.api.v1.ai_providers import router as ai_providers_router
from app.api.v1.ai_routing import router as ai_routing_router
from app.api.v1.ai_usage import router as ai_usage_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.api_usage import router as api_usage_router
from app.api.v1.audit import router as audit_router
from app.api.v1.capacity import router as capacity_router
from app.api.v1.configuration import router as configuration_router
from app.api.v1.deployments import router as deployments_router
from app.api.v1.environments import router as environments_router
from app.api.v1.events import router as events_router
from app.api.v1.incidents import router as incidents_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.logs import router as logs_router
from app.api.v1.operations import router as operations_router
from app.api.v1.performance import router as performance_router
from app.api.v1.queues import router as queues_router
from app.api.v1.security_events import router as security_events_router
from app.api.v1.services import router as services_router
from app.api.v1.system import router as system_router
from app.api.v1.telephony_infrastructure import router as telephony_infra_router
from app.api.v1.workers import router as workers_router

api_v1_router = APIRouter()


# Phase 1 Routers
api_v1_router.include_router(auth_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(customers_router)
api_v1_router.include_router(accounts_router)
api_v1_router.include_router(creditors_router)
api_v1_router.include_router(imports_router)
api_v1_router.include_router(campaigns_router)
api_v1_router.include_router(profile_router)

# Phase 2 Routers
api_v1_router.include_router(ai_agents_router)
api_v1_router.include_router(telephony_router)
api_v1_router.include_router(live_calls_router)
api_v1_router.include_router(ws_router)

# Phase 3 Routers
api_v1_router.include_router(recovery_router)
api_v1_router.include_router(payment_intents_router)
api_v1_router.include_router(ptp_router)
api_v1_router.include_router(callbacks_router)
api_v1_router.include_router(disputes_router)
api_v1_router.include_router(escalations_router)
api_v1_router.include_router(call_analysis_router)
api_v1_router.include_router(calls_analysis_router)
api_v1_router.include_router(automation_router)
api_v1_router.include_router(rules_alias_router)
api_v1_router.include_router(follow_ups_router)
api_v1_router.include_router(analytics_router)
api_v1_router.include_router(exports_router)

# Phase 4 Routers
api_v1_router.include_router(system_router)
api_v1_router.include_router(services_router)
api_v1_router.include_router(workers_router)
api_v1_router.include_router(queues_router)
api_v1_router.include_router(jobs_router)
api_v1_router.include_router(telephony_infra_router)
api_v1_router.include_router(ai_infra_router)
api_v1_router.include_router(ai_providers_router)
api_v1_router.include_router(ai_models_router)
api_v1_router.include_router(ai_routing_router)
api_v1_router.include_router(ai_usage_router)
api_v1_router.include_router(capacity_router)
api_v1_router.include_router(performance_router)
api_v1_router.include_router(incidents_router)
api_v1_router.include_router(alerts_router)
api_v1_router.include_router(deployments_router)
api_v1_router.include_router(environments_router)
api_v1_router.include_router(configuration_router)
api_v1_router.include_router(security_events_router)
api_v1_router.include_router(events_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(operations_router)
api_v1_router.include_router(api_usage_router)
api_v1_router.include_router(logs_router)
api_v1_router.include_router(ai_voice_infra_router)

