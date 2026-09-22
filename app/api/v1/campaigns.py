import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_role
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.analytics import CampaignAnalyticsResponse
from app.schemas.campaign import (
    AddLeadsRequest,
    CampaignActivityItem,
    CampaignCreate,
    CampaignLeadBulk,
    CampaignLeadBulkAction,
    CampaignLeadFilterInput,
    CampaignLeadOut,
    CampaignLeadUpdate,
    CampaignMetricsOut,
    CampaignOut,
    CampaignRunResponse,
    CampaignUpdate,
    CampaignValidationResponse,
    DistributionSet,
    LeadPreviewResult,
)
from app.schemas.common import PaginatedResponse, SingleResponse
from app.services.campaigns import CampaignService
from app.services.recovery.analytics import AnalyticsService
from app.services.recovery.campaign_execution import CampaignExecutionService

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


def _to_campaign_out(c) -> CampaignOut:
    return CampaignOut(
        id=c.id,
        organization_id=c.organization_id,
        name=c.name,
        description=c.description,
        status=c.status,
        campaign_type=c.campaign_type,
        priority=c.priority,
        creditor_id=c.creditor_id,
        ai_agent_id=c.ai_agent_id,
        voice_profile_id=c.voice_profile_id,
        language_mode=c.language_mode,
        timezone=c.timezone,
        calling_start_time=c.calling_start_time,
        calling_end_time=c.calling_end_time,
        start_at=c.start_at,
        end_at=c.end_at,
        max_attempts=c.max_attempts,
        daily_attempt_limit=c.daily_attempt_limit,
        retry_delay_minutes=c.retry_delay_minutes,
        retry_cooldown_minutes=c.retry_cooldown_minutes,
        concurrency_limit=c.concurrency_limit,
        dnc_enforcement=c.dnc_enforcement,
        ai_disclosure_enabled=c.ai_disclosure_enabled,
        recording_disclosure_enabled=c.recording_disclosure_enabled,
        human_escalation_enabled=c.human_escalation_enabled,
        follow_up_enabled=c.follow_up_enabled,
        total_leads=len(c.leads) if hasattr(c, "leads") and c.leads is not None else 0,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


@router.get("", response_model=PaginatedResponse[CampaignOut])
def list_campaigns(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List campaigns with status filtering and pagination."""
    items, total = CampaignService.list_campaigns(
        db=db,
        organization_id=current_user.organization_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[_to_campaign_out(c) for c in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("", response_model=SingleResponse[CampaignOut], status_code=status.HTTP_201_CREATED)
def create_campaign(
    data: CampaignCreate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Create a new recovery campaign with dialing limits and schedule configuration."""
    campaign = CampaignService.create_campaign(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        data=data,
    )
    return SingleResponse(data=_to_campaign_out(campaign))


@router.post("/leads/preview", response_model=SingleResponse[LeadPreviewResult])
def preview_campaign_leads(
    data: CampaignLeadFilterInput,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview eligible debtor accounts based on criteria before attaching to campaign."""
    preview = CampaignService.preview_leads(
        db=db,
        organization_id=current_user.organization_id,
        filters=data,
    )
    return SingleResponse(data=preview)


@router.get("/{campaign_id}", response_model=SingleResponse[CampaignOut])
def get_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details of a campaign."""
    campaign = CampaignService.get_campaign(db, current_user.organization_id, campaign_id)
    return SingleResponse(data=_to_campaign_out(campaign))


@router.patch("/{campaign_id}", response_model=SingleResponse[CampaignOut])
def update_campaign(
    campaign_id: uuid.UUID,
    data: CampaignUpdate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Update campaign parameters or status."""
    campaign = CampaignService.update_campaign(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        campaign_id=campaign_id,
        data=data,
    )
    return SingleResponse(data=_to_campaign_out(campaign))


@router.post("/{campaign_id}/leads", response_model=SingleResponse[dict], status_code=status.HTTP_201_CREATED)
def add_leads_to_campaign(
    campaign_id: uuid.UUID,
    data: AddLeadsRequest,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Attach debtor accounts as leads to a campaign with duplicate checks."""
    added_count = CampaignService.add_leads(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        campaign_id=campaign_id,
        account_ids=data.account_ids,
        priority=data.priority,
    )
    return SingleResponse(data={"added_leads": added_count, "campaign_id": str(campaign_id)})


@router.get("/{campaign_id}/leads", response_model=PaginatedResponse[CampaignLeadOut])
def list_campaign_leads(
    campaign_id: uuid.UUID,
    status: Optional[str] = None,
    contact_state: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List leads attached to a campaign with pagination."""
    items, total = CampaignService.list_campaign_leads(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
        status=status,
        contact_state=contact_state,
        page=page,
        page_size=page_size,
    )
    out_items = [
        CampaignLeadOut(
            id=lead.id,
            campaign_id=lead.campaign_id,
            account_id=lead.account_id,
            account_number=lead.account.account_number if lead.account else None,
            customer_name=lead.account.customer.name if lead.account and lead.account.customer else None,
            outstanding_amount=lead.account.outstanding_amount if lead.account else None,
            status=lead.status,
            priority=lead.priority,
            attempt_count=lead.attempt_count,
            last_attempt_at=lead.last_attempt_at,
            next_attempt_at=lead.next_attempt_at,
            last_outcome=lead.last_outcome,
            contact_state=lead.contact_state,
            created_at=lead.created_at,
        )
        for lead in items
    ]
    return PaginatedResponse(
        items=out_items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.post("/{campaign_id}/leads/bulk-action", response_model=SingleResponse[dict])
def bulk_action_campaign_leads(
    campaign_id: uuid.UUID,
    data: CampaignLeadBulkAction,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Perform bulk operations on campaign leads (retry, skip, reset attempts, change priority)."""
    count = CampaignService.bulk_action_leads(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        campaign_id=campaign_id,
        data=data,
    )
    return SingleResponse(data={"modified_leads": count, "action": data.action})


@router.post("/{campaign_id}/validate", response_model=SingleResponse[CampaignValidationResponse])
def validate_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Pre-flight check verifying agent, voice profile, schedule, and eligible lead availability."""
    validation = CampaignExecutionService.validate_campaign(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
    )
    return SingleResponse(data=validation)


@router.post("/{campaign_id}/start", response_model=SingleResponse[CampaignRunResponse])
def start_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Initiate a campaign run and enqueue eligible leads into dial queue."""
    run = CampaignExecutionService.start_campaign(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=CampaignRunResponse.model_validate(run))


@router.post("/{campaign_id}/pause", response_model=SingleResponse[CampaignRunResponse])
def pause_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Pause an active campaign run."""
    run = CampaignExecutionService.pause_campaign(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=CampaignRunResponse.model_validate(run))


@router.post("/{campaign_id}/resume", response_model=SingleResponse[CampaignRunResponse])
def resume_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Resume a paused campaign run."""
    run = CampaignExecutionService.resume_campaign(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=CampaignRunResponse.model_validate(run))


@router.post("/{campaign_id}/stop", response_model=SingleResponse[CampaignRunResponse])
def stop_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Stop a campaign run and clear queued pending items."""
    run = CampaignExecutionService.stop_campaign(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
        user_id=current_user.id,
    )
    return SingleResponse(data=CampaignRunResponse.model_validate(run))


@router.post("/{campaign_id}/duplicate", response_model=SingleResponse[CampaignOut])
def duplicate_campaign(
    campaign_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Clone an existing campaign as draft."""
    campaign = CampaignService.duplicate_campaign(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        campaign_id=campaign_id,
    )
    return SingleResponse(data=_to_campaign_out(campaign))


@router.get("/{campaign_id}/metrics", response_model=SingleResponse[CampaignMetricsOut])
def get_campaign_metrics(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve detailed execution and funnel metrics for a campaign."""
    metrics = CampaignService.get_campaign_metrics(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
    )
    return SingleResponse(data=metrics)


@router.get("/{campaign_id}/distributions", response_model=SingleResponse[DistributionSet])
def get_campaign_distributions(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve outcome and intent distributions for visualization charts."""
    dist = CampaignService.get_campaign_distributions(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
    )
    return SingleResponse(data=dist)


@router.get("/{campaign_id}/activity", response_model=PaginatedResponse[CampaignActivityItem])
def get_campaign_activity(
    campaign_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve recent operational activity log for a campaign."""
    items, total = CampaignService.get_campaign_activity(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{campaign_id}/analytics", response_model=SingleResponse[CampaignAnalyticsResponse])
def get_campaign_analytics(
    campaign_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve full analytics report for a campaign."""
    analytics = AnalyticsService.get_campaign_analytics(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
    )
    return SingleResponse(data=analytics)


@router.patch("/{campaign_id}/leads/{lead_id}", response_model=SingleResponse[CampaignLeadOut])
def update_campaign_lead(
    campaign_id: uuid.UUID,
    lead_id: uuid.UUID,
    data: CampaignLeadUpdate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Update single lead status or priority."""
    lead = CampaignService.update_lead(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
        lead_id=lead_id,
        data=data,
    )
    return SingleResponse(
        data=CampaignLeadOut(
            id=lead.id,
            campaign_id=lead.campaign_id,
            account_id=lead.account_id,
            account_number=lead.account.account_number if lead.account else None,
            customer_name=lead.account.customer.name if lead.account and lead.account.customer else None,
            outstanding_amount=lead.account.outstanding_amount if lead.account else None,
            status=lead.status,
            priority=lead.priority,
            attempt_count=lead.attempt_count,
            last_attempt_at=lead.last_attempt_at,
            next_attempt_at=lead.next_attempt_at,
            last_outcome=lead.last_outcome,
            contact_state=lead.contact_state,
            created_at=lead.created_at,
        )
    )


@router.delete("/{campaign_id}/leads/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_campaign_lead(
    campaign_id: uuid.UUID,
    lead_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Remove lead from campaign."""
    CampaignService.delete_lead(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
        lead_id=lead_id,
    )


@router.post("/{campaign_id}/leads/bulk", response_model=SingleResponse[dict])
def bulk_campaign_lead_action(
    campaign_id: uuid.UUID,
    data: CampaignLeadBulk,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Apply bulk action (add_to_queue, remove, pause, resume) to campaign leads."""
    updated = CampaignService.bulk_action_leads_v3(
        db=db,
        organization_id=current_user.organization_id,
        campaign_id=campaign_id,
        action=data.action,
        lead_ids=data.lead_ids,
    )
    return SingleResponse(data={"updated": updated})
