import uuid
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictException, NotFoundException, ValidationException
from app.db.models.account import Account
from app.db.models.audit import AuditLog
from app.db.models.campaign import Campaign, CampaignLead
from app.schemas.campaign import CampaignCreate, CampaignLeadBulkAction, CampaignUpdate
from app.utils.pagination import paginate


class CampaignService:
    @staticmethod
    def list_campaigns(
        db: Session,
        organization_id: uuid.UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[Campaign], int]:
        query = select(Campaign).where(Campaign.organization_id == organization_id)
        if status:
            query = query.where(Campaign.status == status)

        query = query.order_by(Campaign.created_at.desc())
        return paginate(db, query, page=page, page_size=page_size)

    @staticmethod
    def get_campaign(db: Session, organization_id: uuid.UUID, campaign_id: uuid.UUID) -> Campaign:
        stmt = select(Campaign).where(
            Campaign.id == campaign_id,
            Campaign.organization_id == organization_id,
        )
        campaign = db.scalar(stmt)
        if not campaign:
            raise NotFoundException("Campaign not found", code="CAMPAIGN_NOT_FOUND")
        return campaign

    @staticmethod
    def create_campaign(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        data: CampaignCreate,
    ) -> Campaign:
        if data.calling_start_time >= data.calling_end_time:
            raise ValidationException("Calling start time must be earlier than calling end time")

        campaign = Campaign(
            organization_id=organization_id,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            campaign_type=data.campaign_type,
            priority=data.priority,
            creditor_id=data.creditor_id,
            ai_agent_id=data.ai_agent_id,
            voice_profile_id=data.voice_profile_id,
            language_mode=data.language_mode,
            timezone=data.timezone,
            calling_start_time=data.calling_start_time,
            calling_end_time=data.calling_end_time,
            start_at=data.start_at,
            end_at=data.end_at,
            max_attempts=data.max_attempts,
            daily_attempt_limit=data.daily_attempt_limit,
            retry_delay_minutes=data.retry_delay_minutes,
            retry_cooldown_minutes=data.retry_cooldown_minutes,
            concurrency_limit=data.concurrency_limit,
            dnc_enforcement=data.dnc_enforcement,
            ai_disclosure_enabled=data.ai_disclosure_enabled,
            recording_disclosure_enabled=data.recording_disclosure_enabled,
            human_escalation_enabled=data.human_escalation_enabled,
            follow_up_enabled=data.follow_up_enabled,
            created_by=user_id,
            status="draft",
        )
        db.add(campaign)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_CAMPAIGN",
            entity_type="CAMPAIGN",
            entity_id=campaign.id,
        )
        db.add(audit)
        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def update_campaign(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        campaign_id: uuid.UUID,
        data: CampaignUpdate,
    ) -> Campaign:
        campaign = CampaignService.get_campaign(db, organization_id, campaign_id)

        if data.name is not None:
            campaign.name = data.name.strip()
        if data.description is not None:
            campaign.description = data.description.strip()
        if data.campaign_type is not None:
            campaign.campaign_type = data.campaign_type
        if data.priority is not None:
            campaign.priority = data.priority
        if data.creditor_id is not None:
            campaign.creditor_id = data.creditor_id
        if data.ai_agent_id is not None:
            campaign.ai_agent_id = data.ai_agent_id
        if data.voice_profile_id is not None:
            campaign.voice_profile_id = data.voice_profile_id
        if data.language_mode is not None:
            campaign.language_mode = data.language_mode
        if data.status is not None:
            campaign.status = data.status
        if data.timezone is not None:
            campaign.timezone = data.timezone
        if data.calling_start_time is not None:
            campaign.calling_start_time = data.calling_start_time
        if data.calling_end_time is not None:
            campaign.calling_end_time = data.calling_end_time
        if data.start_at is not None:
            campaign.start_at = data.start_at
        if data.end_at is not None:
            campaign.end_at = data.end_at
        if data.max_attempts is not None:
            campaign.max_attempts = data.max_attempts
        if data.daily_attempt_limit is not None:
            campaign.daily_attempt_limit = data.daily_attempt_limit
        if data.retry_delay_minutes is not None:
            campaign.retry_delay_minutes = data.retry_delay_minutes
        if data.retry_cooldown_minutes is not None:
            campaign.retry_cooldown_minutes = data.retry_cooldown_minutes
        if data.concurrency_limit is not None:
            campaign.concurrency_limit = data.concurrency_limit
        if data.dnc_enforcement is not None:
            campaign.dnc_enforcement = data.dnc_enforcement
        if data.ai_disclosure_enabled is not None:
            campaign.ai_disclosure_enabled = data.ai_disclosure_enabled
        if data.recording_disclosure_enabled is not None:
            campaign.recording_disclosure_enabled = data.recording_disclosure_enabled
        if data.human_escalation_enabled is not None:
            campaign.human_escalation_enabled = data.human_escalation_enabled
        if data.follow_up_enabled is not None:
            campaign.follow_up_enabled = data.follow_up_enabled

        if campaign.calling_start_time >= campaign.calling_end_time:
            raise ValidationException("Calling start time must be earlier than calling end time")

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="UPDATE_CAMPAIGN",
            entity_type="CAMPAIGN",
            entity_id=campaign.id,
        )
        db.add(audit)
        db.commit()
        db.refresh(campaign)
        return campaign

    @staticmethod
    def add_leads(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        campaign_id: uuid.UUID,
        account_ids: List[uuid.UUID],
        priority: int = 1,
    ) -> int:
        campaign = CampaignService.get_campaign(db, organization_id, campaign_id)

        if not account_ids:
            return 0

        # Verify all accounts exist and belong to the same organization
        valid_accounts = db.scalars(
            select(Account.id).where(
                Account.id.in_(account_ids),
                Account.organization_id == organization_id,
            )
        ).all()
        valid_acc_set = set(valid_accounts)

        missing = set(account_ids) - valid_acc_set
        if missing:
            raise NotFoundException(
                f"One or more accounts not found or do not belong to this organization: {list(missing)[:3]}"
            )

        # Check existing leads in this campaign
        existing_leads = db.scalars(
            select(CampaignLead.account_id).where(
                CampaignLead.campaign_id == campaign_id,
                CampaignLead.account_id.in_(account_ids),
            )
        ).all()
        existing_lead_set = set(existing_leads)

        new_acc_ids = [acc_id for acc_id in account_ids if acc_id not in existing_lead_set]
        if not new_acc_ids and account_ids:
            raise ConflictException("All requested accounts are already attached to this campaign", code="DUPLICATE_LEADS")

        new_leads = [
            CampaignLead(
                campaign_id=campaign.id,
                account_id=acc_id,
                priority=priority,
                status="pending",
                attempt_count=0,
                contact_state="uncontacted",
            )
            for acc_id in new_acc_ids
        ]
        db.add_all(new_leads)

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="ADD_CAMPAIGN_LEADS",
            entity_type="CAMPAIGN",
            entity_id=campaign.id,
            metadata_json={"added_count": len(new_leads)},
        )
        db.add(audit)
        db.commit()
        return len(new_leads)

    @staticmethod
    def list_campaign_leads(
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
        status: Optional[str] = None,
        contact_state: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[CampaignLead], int]:
        campaign = CampaignService.get_campaign(db, organization_id, campaign_id)

        query = select(CampaignLead).where(CampaignLead.campaign_id == campaign.id)
        if status:
            query = query.where(CampaignLead.status == status)
        if contact_state:
            query = query.where(CampaignLead.contact_state == contact_state)

        query = query.order_by(CampaignLead.created_at.desc())
        return paginate(db, query, page=page, page_size=page_size)

    @staticmethod
    def bulk_action_leads(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        campaign_id: uuid.UUID,
        data: CampaignLeadBulkAction,
    ) -> int:
        campaign = CampaignService.get_campaign(db, organization_id, campaign_id)
        stmt = select(CampaignLead).where(
            CampaignLead.campaign_id == campaign.id,
            CampaignLead.id.in_(data.lead_ids),
        )
        leads = db.scalars(stmt).all()
        if not leads:
            return 0

        for lead in leads:
            if data.action == "retry":
                lead.status = "pending"
            elif data.action == "skip":
                lead.status = "skipped"
            elif data.action == "reset_attempts":
                lead.attempt_count = 0
                lead.status = "pending"
            elif data.action == "change_priority":
                if data.priority is not None:
                    lead.priority = data.priority

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="BULK_ACTION_CAMPAIGN_LEADS",
            entity_type="CAMPAIGN",
            entity_id=campaign.id,
            metadata_json={"action": data.action, "count": len(leads)},
        )
        db.add(audit)
        db.commit()
        return len(leads)

    @staticmethod
    def duplicate_campaign(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        campaign_id: uuid.UUID,
    ) -> Campaign:
        original = CampaignService.get_campaign(db, organization_id, campaign_id)
        duplicated = Campaign(
            organization_id=organization_id,
            name=f"{original.name} (Copy)",
            description=original.description,
            campaign_type=original.campaign_type,
            priority=original.priority,
            creditor_id=original.creditor_id,
            ai_agent_id=original.ai_agent_id,
            voice_profile_id=original.voice_profile_id,
            language_mode=original.language_mode,
            timezone=original.timezone,
            calling_start_time=original.calling_start_time,
            calling_end_time=original.calling_end_time,
            start_at=original.start_at,
            end_at=original.end_at,
            max_attempts=original.max_attempts,
            daily_attempt_limit=original.daily_attempt_limit,
            retry_delay_minutes=original.retry_delay_minutes,
            retry_cooldown_minutes=original.retry_cooldown_minutes,
            concurrency_limit=original.concurrency_limit,
            dnc_enforcement=original.dnc_enforcement,
            ai_disclosure_enabled=original.ai_disclosure_enabled,
            recording_disclosure_enabled=original.recording_disclosure_enabled,
            human_escalation_enabled=original.human_escalation_enabled,
            follow_up_enabled=original.follow_up_enabled,
            created_by=user_id,
            status="draft",
        )
        db.add(duplicated)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="DUPLICATE_CAMPAIGN",
            entity_type="CAMPAIGN",
            entity_id=duplicated.id,
            metadata_json={"source_campaign_id": str(original.id)},
        )
        db.add(audit)
        db.commit()
        db.refresh(duplicated)
        return duplicated

    @staticmethod
    def get_campaign_metrics(
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ):
        from app.schemas.campaign import CampaignMetricsOut
        from app.db.models.recovery_outcome import RecoveryOutcome
        from app.db.models.automation import FollowUpJob
        from app.db.models.call import Call

        campaign = CampaignService.get_campaign(db, organization_id, campaign_id)
        leads = db.scalars(
            select(CampaignLead).where(CampaignLead.campaign_id == campaign_id)
        ).all()

        total_leads = len(leads)
        pending = sum(1 for l in leads if l.status in ("pending", "queued"))
        attempted = sum(1 for l in leads if l.attempt_count > 0)
        connected = sum(1 for l in leads if l.contact_state in ("contacted", "in_progress", "completed"))

        outcomes = db.scalars(
            select(RecoveryOutcome).where(RecoveryOutcome.campaign_id == campaign_id)
        ).all()

        promised = sum(1 for o in outcomes if o.outcome_type == "ptp")
        paid = sum(1 for o in outcomes if o.outcome_type == "paid")
        disputed = sum(1 for o in outcomes if o.outcome_type == "dispute")
        callbacks = sum(1 for o in outcomes if o.outcome_type == "callback_requested")
        escalations = sum(1 for o in outcomes if o.outcome_type == "escalated")

        follow_ups_pending = db.scalar(
            select(func.count(FollowUpJob.id)).where(
                FollowUpJob.organization_id == organization_id,
                FollowUpJob.status == "scheduled",
            )
        ) or 0

        calls_count = 0
        if campaign_id:
            calls_count = db.scalar(
                select(func.count(Call.id)).where(Call.campaign_id == campaign_id)
            ) or 0

        return CampaignMetricsOut(
            campaign_id=campaign.id,
            total_leads=total_leads,
            pending=pending,
            attempted=attempted,
            connected=connected,
            conversations=calls_count,
            promised=promised,
            paid=paid,
            disputed=disputed,
            callbacks=callbacks,
            escalations=escalations,
            follow_ups_pending=follow_ups_pending,
        )

    @staticmethod
    def get_campaign_distributions(
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ):
        from app.schemas.campaign import DistributionSet, OutcomeCount, IntentCount
        from app.db.models.recovery_outcome import RecoveryOutcome
        from app.db.models.call import Call
        from app.db.models.payment_intent import PaymentIntent

        campaign = CampaignService.get_campaign(db, organization_id, campaign_id)

        # Recovery outcomes
        outcome_rows = db.execute(
            select(RecoveryOutcome.outcome_type, func.count(RecoveryOutcome.id))
            .where(RecoveryOutcome.campaign_id == campaign_id)
            .group_by(RecoveryOutcome.outcome_type)
        ).all()
        recovery_outcomes = [
            OutcomeCount(outcome=row[0], count=row[1]) for row in outcome_rows
        ]

        # Call outcomes / dispositions
        call_rows = db.execute(
            select(func.coalesce(Call.disposition, Call.status), func.count(Call.id))
            .where(Call.campaign_id == campaign_id)
            .group_by(func.coalesce(Call.disposition, Call.status))
        ).all()
        call_outcomes = [
            OutcomeCount(outcome=row[0] or "unknown", count=row[1]) for row in call_rows
        ]

        # Payment intents
        leads = db.scalars(
            select(CampaignLead.account_id).where(CampaignLead.campaign_id == campaign_id)
        ).all()
        payment_intents = []
        if leads:
            intent_rows = db.execute(
                select(PaymentIntent.status, func.count(PaymentIntent.id))
                .where(PaymentIntent.account_id.in_(leads))
                .group_by(PaymentIntent.status)
            ).all()
            payment_intents = [
                IntentCount(intent=row[0], count=row[1]) for row in intent_rows
            ]

        return DistributionSet(
            recovery_outcomes=recovery_outcomes,
            call_outcomes=call_outcomes,
            payment_intents=payment_intents,
        )

    @staticmethod
    def get_campaign_activity(
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
        page: int = 1,
        page_size: int = 25,
    ):
        from app.schemas.campaign import CampaignActivityItem
        campaign = CampaignService.get_campaign(db, organization_id, campaign_id)
        query = (
            select(AuditLog)
            .where(
                AuditLog.organization_id == organization_id,
                AuditLog.entity_id == campaign_id,
            )
            .order_by(AuditLog.created_at.desc())
        )
        logs, total = paginate(db, query, page=page, page_size=page_size)
        items = [
            CampaignActivityItem(
                id=log.id,
                campaign_id=campaign.id,
                action=log.action,
                actor=str(log.user_id) if log.user_id else "System",
                detail=str(log.metadata_json) if log.metadata_json else None,
                created_at=log.created_at,
            )
            for log in logs
        ]
        return items, total

    @staticmethod
    def preview_leads(
        db: Session,
        organization_id: uuid.UUID,
        filters,
    ):
        from app.schemas.campaign import LeadFilterStats, LeadPreviewResult
        from app.db.models.customer import CustomerPhone

        query = select(Account).where(
            Account.organization_id == organization_id,
            Account.status == "active",
        )
        if filters.creditor_id:
            query = query.where(Account.creditor_id == filters.creditor_id)
        if filters.min_outstanding is not None:
            query = query.where(Account.outstanding_amount >= filters.min_outstanding)
        if filters.max_outstanding is not None:
            query = query.where(Account.outstanding_amount <= filters.max_outstanding)

        accounts = db.scalars(query.limit(500)).all()
        account_ids = [acc.id for acc in accounts]

        # Check phone numbers
        eligible_ids = []
        blocked_count = 0
        for acc in accounts:
            phone_count = db.scalar(
                select(func.count(CustomerPhone.id)).where(
                    CustomerPhone.customer_id == acc.customer_id
                )
            ) or 0
            if phone_count > 0:
                eligible_ids.append(acc.id)
            else:
                blocked_count += 1

        stats = LeadFilterStats(
            total=len(accounts),
            eligible=len(eligible_ids),
            blocked=blocked_count,
            warnings=0,
            errors=0,
        )
        return LeadPreviewResult(stats=stats, account_ids=eligible_ids)

    @staticmethod
    def update_lead(
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
        lead_id: uuid.UUID,
        data,
    ) -> CampaignLead:
        campaign = CampaignService.get_campaign(db, organization_id, campaign_id)
        stmt = select(CampaignLead).where(
            CampaignLead.id == lead_id,
            CampaignLead.campaign_id == campaign.id,
        )
        lead = db.scalar(stmt)
        if not lead:
            raise NotFoundException("Lead not found", code="LEAD_NOT_FOUND")

        if data.status is not None:
            lead.status = data.status
        if data.priority is not None:
            lead.priority = data.priority

        db.commit()
        db.refresh(lead)
        return lead

    @staticmethod
    def delete_lead(
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
        lead_id: uuid.UUID,
    ):
        campaign = CampaignService.get_campaign(db, organization_id, campaign_id)
        stmt = select(CampaignLead).where(
            CampaignLead.id == lead_id,
            CampaignLead.campaign_id == campaign.id,
        )
        lead = db.scalar(stmt)
        if not lead:
            raise NotFoundException("Lead not found", code="LEAD_NOT_FOUND")

        db.delete(lead)
        db.commit()

    @staticmethod
    def bulk_action_leads_v3(
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
        action: str,
        lead_ids: List[uuid.UUID],
    ) -> int:
        campaign = CampaignService.get_campaign(db, organization_id, campaign_id)
        stmt = select(CampaignLead).where(
            CampaignLead.campaign_id == campaign.id,
            CampaignLead.id.in_(lead_ids),
        )
        leads = db.scalars(stmt).all()
        if not leads:
            return 0

        if action == "remove":
            for lead in leads:
                db.delete(lead)
            db.commit()
            return len(leads)

        for lead in leads:
            if action == "add_to_queue":
                lead.status = "queued"
            elif action == "pause":
                lead.status = "paused"
            elif action == "resume":
                lead.status = "pending"

        db.commit()
        return len(leads)
