import uuid
from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException
from app.db.models.account import Account, AccountPayment
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.dial_queue import DialQueueItem
from app.db.models.dispute import Dispute
from app.db.models.escalation import Escalation
from app.db.models.promise_to_pay import PromiseToPay
from app.db.models.recovery_outcome import RecoveryOutcome
from app.schemas.analytics import (
    CampaignAnalyticsResponse,
    QueueMetricsResponse,
    RecoveryMetricsResponse,
)


class AnalyticsService:
    @classmethod
    def get_campaign_analytics(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
    ) -> CampaignAnalyticsResponse:
        campaign = db.scalar(
            select(Campaign).where(
                Campaign.id == campaign_id,
                Campaign.organization_id == organization_id,
            )
        )
        if not campaign:
            raise NotFoundException("Campaign not found", code="CAMPAIGN_NOT_FOUND")

        leads = db.scalars(
            select(CampaignLead).where(CampaignLead.campaign_id == campaign_id)
        ).all()
        total_leads = len(leads)
        attempted_leads = sum(1 for l in leads if l.attempt_count > 0)
        contacted_leads = sum(1 for l in leads if l.contact_state not in ("uncontacted", "unreachable"))

        # Outcomes for this campaign
        outcomes = db.scalars(
            select(RecoveryOutcome).where(RecoveryOutcome.campaign_id == campaign_id)
        ).all()

        ptp_count = sum(1 for o in outcomes if o.outcome_type == "ptp")
        paid_count = sum(1 for o in outcomes if o.outcome_type == "paid")
        dispute_count = sum(1 for o in outcomes if o.outcome_type == "dispute")
        callback_count = sum(1 for o in outcomes if o.outcome_type == "callback_requested")
        escalated_count = sum(1 for o in outcomes if o.outcome_type == "escalated")

        # Sum ptp amount for this campaign
        lead_account_ids = [l.account_id for l in leads]
        ptp_amount = db.scalar(
            select(func.coalesce(func.sum(PromiseToPay.amount), Decimal("0.00"))).where(
                PromiseToPay.account_id.in_(lead_account_ids),
                PromiseToPay.organization_id == organization_id,
            )
        ) if lead_account_ids else Decimal("0.00")

        # Sum payments for accounts in this campaign
        paid_amount = db.scalar(
            select(func.coalesce(func.sum(AccountPayment.amount), Decimal("0.00"))).where(
                AccountPayment.account_id.in_(lead_account_ids)
            )
        ) if lead_account_ids else Decimal("0.00")

        # Total outstanding amount
        total_outstanding = db.scalar(
            select(func.coalesce(func.sum(Account.outstanding_amount), Decimal("0.00"))).where(
                Account.id.in_(lead_account_ids)
            )
        ) if lead_account_ids else Decimal("0.00")

        contact_rate = float(contacted_leads / total_leads * 100) if total_leads > 0 else 0.0
        ptp_conversion_rate = float(ptp_count / contacted_leads * 100) if contacted_leads > 0 else 0.0
        total_potential = total_outstanding + paid_amount
        recovery_rate = (
            float(paid_amount / total_potential * 100) if total_potential > Decimal("0.00") else 0.0
        )

        return CampaignAnalyticsResponse(
            campaign_id=campaign.id,
            campaign_name=campaign.name,
            total_leads=total_leads,
            attempted_leads=attempted_leads,
            contacted_leads=contacted_leads,
            ptp_count=ptp_count,
            ptp_amount=ptp_amount,
            paid_count=paid_count,
            paid_amount=paid_amount,
            dispute_count=dispute_count,
            callback_count=callback_count,
            escalated_count=escalated_count,
            contact_rate=round(contact_rate, 2),
            ptp_conversion_rate=round(ptp_conversion_rate, 2),
            recovery_rate=round(recovery_rate, 2),
        )

    @classmethod
    def get_recovery_metrics(
        cls,
        db: Session,
        organization_id: uuid.UUID,
    ) -> RecoveryMetricsResponse:
        outcomes = db.scalars(
            select(RecoveryOutcome).where(RecoveryOutcome.organization_id == organization_id)
        ).all()
        total_outcomes = len(outcomes)

        ptp_count = sum(1 for o in outcomes if o.outcome_type == "ptp")
        paid_count = sum(1 for o in outcomes if o.outcome_type == "paid")
        dispute_count = sum(1 for o in outcomes if o.outcome_type == "dispute")
        callback_count = sum(1 for o in outcomes if o.outcome_type == "callback_requested")
        escalated_count = sum(1 for o in outcomes if o.outcome_type == "escalated")
        unreachable_count = sum(1 for o in outcomes if o.outcome_type == "unreachable")
        refused_count = sum(1 for o in outcomes if o.outcome_type == "refused")
        other_count = total_outcomes - (
            ptp_count + paid_count + dispute_count + callback_count + escalated_count + unreachable_count + refused_count
        )

        total_outstanding = db.scalar(
            select(func.coalesce(func.sum(Account.outstanding_amount), Decimal("0.00"))).where(
                Account.organization_id == organization_id
            )
        ) or Decimal("0.00")

        total_ptp_amount = db.scalar(
            select(func.coalesce(func.sum(PromiseToPay.amount), Decimal("0.00"))).where(
                PromiseToPay.organization_id == organization_id
            )
        ) or Decimal("0.00")

        # Total collected across organization accounts
        org_account_ids = select(Account.id).where(Account.organization_id == organization_id)
        total_collected = db.scalar(
            select(func.coalesce(func.sum(AccountPayment.amount), Decimal("0.00"))).where(
                AccountPayment.account_id.in_(org_account_ids)
            )
        ) or Decimal("0.00")

        # Kept PTP count
        kept_ptps = db.scalar(
            select(func.count(PromiseToPay.id)).where(
                PromiseToPay.organization_id == organization_id,
                PromiseToPay.status == "kept",
            )
        ) or 0
        total_ptp_records = db.scalar(
            select(func.count(PromiseToPay.id)).where(
                PromiseToPay.organization_id == organization_id
            )
        ) or 0

        dispute_rate = float(dispute_count / total_outcomes * 100) if total_outcomes > 0 else 0.0
        escalation_rate = float(escalated_count / total_outcomes * 100) if total_outcomes > 0 else 0.0
        ptp_kept_rate = float(kept_ptps / total_ptp_records * 100) if total_ptp_records > 0 else 0.0

        return RecoveryMetricsResponse(
            total_outcomes=total_outcomes,
            ptp_count=ptp_count,
            paid_count=paid_count,
            dispute_count=dispute_count,
            callback_count=callback_count,
            escalated_count=escalated_count,
            unreachable_count=unreachable_count,
            refused_count=refused_count,
            other_count=other_count,
            total_outstanding=total_outstanding,
            total_ptp_amount=total_ptp_amount,
            total_collected_amount=total_collected,
            dispute_rate=round(dispute_rate, 2),
            escalation_rate=round(escalation_rate, 2),
            ptp_kept_rate=round(ptp_kept_rate, 2),
        )

    @classmethod
    def get_queue_metrics(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: Optional[uuid.UUID] = None,
    ) -> QueueMetricsResponse:
        stmt = select(DialQueueItem).where(DialQueueItem.organization_id == organization_id)
        if campaign_id:
            stmt = stmt.where(DialQueueItem.campaign_id == campaign_id)

        items = db.scalars(stmt).all()
        total_queued = len(items)

        pending_count = sum(1 for i in items if i.status == "pending")
        reserved_count = sum(1 for i in items if i.status == "reserved")
        dialing_count = sum(1 for i in items if i.status == "dialing")
        completed_count = sum(1 for i in items if i.status == "completed")
        failed_count = sum(1 for i in items if i.status == "failed")
        expired_count = sum(1 for i in items if i.status == "expired")

        retry_distribution: Dict[int, int] = {}
        for item in items:
            retry_distribution[item.retry_count] = retry_distribution.get(item.retry_count, 0) + 1

        return QueueMetricsResponse(
            total_queued=total_queued,
            pending_count=pending_count,
            reserved_count=reserved_count,
            dialing_count=dialing_count,
            completed_count=completed_count,
            failed_count=failed_count,
            expired_count=expired_count,
            retry_distribution=retry_distribution,
        )
