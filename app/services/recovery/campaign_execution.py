import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictException, NotFoundException, ValidationException
from app.db.models.ai_agent import AiAgent, VoiceProfile
from app.db.models.audit import AuditLog
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.campaign_run import CampaignRun
from app.db.models.dial_queue import DialQueueItem
from app.schemas.campaign import CampaignValidationIssue, CampaignValidationResponse
from app.services.recovery.calling_window import CallingWindowService
from app.services.recovery.eligibility import LeadEligibilityService
from app.services.recovery.queue import DialQueueService


class CampaignExecutionService:
    @classmethod
    def validate_campaign(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> CampaignValidationResponse:
        stmt = select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.organization_id == organization_id,
        )
        campaign = db.scalar(stmt)
        if not campaign:
            raise NotFoundException("Campaign not found", code="CAMPAIGN_NOT_FOUND")

        issues: List[CampaignValidationIssue] = []

        # 1. Agent validation
        if campaign.ai_agent_id:
            agent = db.scalar(
                select(AiAgent).where(
                    AiAgent.id == campaign.ai_agent_id,
                    AiAgent.organization_id == organization_id,
                )
            )
            if not agent:
                issues.append(CampaignValidationIssue(severity="error", code="AGENT_NOT_FOUND", message="Configured AI Agent was not found."))
            elif not agent.is_active:
                issues.append(CampaignValidationIssue(severity="error", code="AGENT_INACTIVE", message="Configured AI Agent is inactive."))
        else:
            issues.append(CampaignValidationIssue(severity="warning", code="NO_AGENT_ASSIGNED", message="No AI agent assigned to campaign."))

        # 2. Voice profile validation
        if campaign.voice_profile_id:
            voice = db.scalar(
                select(VoiceProfile).where(
                    VoiceProfile.id == campaign.voice_profile_id,
                    VoiceProfile.organization_id == organization_id,
                )
            )
            if not voice:
                issues.append(CampaignValidationIssue(severity="error", code="VOICE_NOT_FOUND", message="Configured voice profile was not found."))
            elif voice.status != "ready":
                issues.append(CampaignValidationIssue(severity="error", code="VOICE_NOT_READY", message="Voice profile is not in 'ready' status."))

        # 3. Calling window
        if campaign.calling_start_time >= campaign.calling_end_time:
            issues.append(CampaignValidationIssue(severity="error", code="INVALID_HOURS", message="Calling start time must precede end time."))

        # 4. Lead count and eligibility evaluation
        leads = db.scalars(
            select(CampaignLead).where(CampaignLead.campaign_id == campaign.id)
        ).all()
        total_leads = len(leads)

        if total_leads == 0:
            issues.append(CampaignValidationIssue(severity="error", code="NO_LEADS", message="Campaign has no attached leads."))

        eligible_count = 0
        now = datetime.now(timezone.utc)
        for lead in leads:
            is_eligible, _, _ = LeadEligibilityService.evaluate_lead(db, campaign, lead, at_time=now)
            if is_eligible:
                eligible_count += 1

        if total_leads > 0 and eligible_count == 0:
            issues.append(CampaignValidationIssue(severity="warning", code="ZERO_ELIGIBLE_LEADS", message="No leads currently eligible to dial."))

        has_errors = any(i.severity == "error" for i in issues)
        return CampaignValidationResponse(
            valid=not has_errors,
            total_leads=total_leads,
            eligible_leads=eligible_count,
            issues=issues,
        )

    @classmethod
    def start_campaign(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> CampaignRun:
        validation = cls.validate_campaign(db, organization_id, campaign_id)
        if not validation.valid:
            error_msgs = [i.message for i in validation.issues if i.severity == "error"]
            raise ValidationException(f"Campaign validation failed: {'; '.join(error_msgs)}")

        campaign = db.get(Campaign, campaign_id)
        if not campaign:
            raise NotFoundException("Campaign not found", code="CAMPAIGN_NOT_FOUND")

        if campaign.status == "running":
            raise ConflictException("Campaign is already running", code="CAMPAIGN_ALREADY_RUNNING")

        now = datetime.now(timezone.utc)

        run = CampaignRun(
            organization_id=organization_id,
            campaign_id=campaign.id,
            run_number=1,
            status="active",
            started_at=now,
            total_leads=validation.total_leads,
        )
        db.add(run)
        db.flush()

        # Enqueue eligible leads
        leads = db.scalars(
            select(CampaignLead).where(CampaignLead.campaign_id == campaign.id)
        ).all()

        enqueued_count = 0
        for lead in leads:
            is_eligible, _, phone = LeadEligibilityService.evaluate_lead(db, campaign, lead, at_time=now)
            if is_eligible and phone:
                DialQueueService.enqueue_lead(
                    db=db,
                    organization_id=organization_id,
                    campaign_id=campaign.id,
                    lead=lead,
                    phone_number=phone,
                    campaign_run_id=run.id,
                    priority=lead.priority,
                )
                enqueued_count += 1

        campaign.status = "running"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="START_CAMPAIGN",
            entity_type="CAMPAIGN",
            entity_id=campaign.id,
            metadata_json={"run_id": str(run.id), "enqueued_leads": enqueued_count},
        )
        db.add(audit)
        db.commit()
        db.refresh(run)
        return run

    @classmethod
    def pause_campaign(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> CampaignRun:
        campaign = db.scalar(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == organization_id,
            )
        )
        if not campaign:
            raise NotFoundException("Campaign not found", code="CAMPAIGN_NOT_FOUND")

        if campaign.status != "running":
            raise ConflictException("Campaign is not running", code="CAMPAIGN_NOT_RUNNING")

        now = datetime.now(timezone.utc)
        run = db.scalar(
            select(CampaignRun)
            .where(CampaignRun.campaign_id == campaign.id, CampaignRun.status == "active")
            .order_by(CampaignRun.created_at.desc())
        )
        if run:
            run.status = "paused"
            run.paused_at = now

        campaign.status = "paused"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="PAUSE_CAMPAIGN",
            entity_type="CAMPAIGN",
            entity_id=campaign.id,
        )
        db.add(audit)
        db.commit()
        if run:
            db.refresh(run)
            return run
        return CampaignRun(organization_id=organization_id, campaign_id=campaign.id, status="paused")

    @classmethod
    def resume_campaign(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> CampaignRun:
        campaign = db.scalar(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == organization_id,
            )
        )
        if not campaign:
            raise NotFoundException("Campaign not found", code="CAMPAIGN_NOT_FOUND")

        if campaign.status != "paused":
            raise ConflictException("Campaign is not paused", code="CAMPAIGN_NOT_PAUSED")

        run = db.scalar(
            select(CampaignRun)
            .where(CampaignRun.campaign_id == campaign.id, CampaignRun.status == "paused")
            .order_by(CampaignRun.created_at.desc())
        )
        if run:
            run.status = "active"
            run.paused_at = None

        campaign.status = "running"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="RESUME_CAMPAIGN",
            entity_type="CAMPAIGN",
            entity_id=campaign.id,
        )
        db.add(audit)
        db.commit()
        if run:
            db.refresh(run)
            return run
        return CampaignRun(organization_id=organization_id, campaign_id=campaign.id, status="active")

    @classmethod
    def stop_campaign(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> CampaignRun:
        campaign = db.scalar(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == organization_id,
            )
        )
        if not campaign:
            raise NotFoundException("Campaign not found", code="CAMPAIGN_NOT_FOUND")

        now = datetime.now(timezone.utc)
        run = db.scalar(
            select(CampaignRun)
            .where(CampaignRun.campaign_id == campaign.id, CampaignRun.status.in_(("active", "paused")))
            .order_by(CampaignRun.created_at.desc())
        )
        if run:
            run.status = "completed"
            run.completed_at = now

        # Remove pending items from dial queue for this campaign
        db.execute(
            delete(DialQueueItem).where(
                DialQueueItem.campaign_id == campaign.id,
                DialQueueItem.status == "pending",
            )
        )

        campaign.status = "completed"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="STOP_CAMPAIGN",
            entity_type="CAMPAIGN",
            entity_id=campaign.id,
        )
        db.add(audit)
        db.commit()
        if run:
            db.refresh(run)
            return run
        return CampaignRun(organization_id=organization_id, campaign_id=campaign.id, status="completed")
