import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException
from app.db.models.account import Account
from app.db.models.audit import AuditLog
from app.db.models.call import Call
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.customer import Customer
from app.db.models.recovery_outcome import RecoveryOutcome
from app.schemas.recovery import RecoveryOutcomeCreate, RecoverySummary
from app.services.recovery.retry import RetryScheduler
from app.utils.pagination import paginate


class RecoveryOutcomeService:
    @classmethod
    def record_outcome(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        data: RecoveryOutcomeCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> RecoveryOutcome:
        # Validate customer and account
        customer = db.scalar(
            select(Customer).where(
                Customer.id == data.customer_id,
                Customer.organization_id == organization_id,
            )
        )
        if not customer:
            raise NotFoundException("Customer not found", code="CUSTOMER_NOT_FOUND")

        account = db.scalar(
            select(Account).where(
                Account.id == data.account_id,
                Account.organization_id == organization_id,
            )
        )
        if not account:
            raise NotFoundException("Account not found", code="ACCOUNT_NOT_FOUND")

        # Create authoritative outcome
        outcome = RecoveryOutcome(
            organization_id=organization_id,
            call_id=data.call_id,
            customer_id=data.customer_id,
            account_id=data.account_id,
            campaign_id=data.campaign_id,
            outcome_type=data.outcome_type.lower(),
            details=data.details or {},
            notes=data.notes,
            recorded_by=data.recorded_by,
        )
        db.add(outcome)
        db.flush()

        # If associated with a campaign lead, update lead progress
        if data.campaign_id:
            lead = db.scalar(
                select(CampaignLead).where(
                    CampaignLead.campaign_id == data.campaign_id,
                    CampaignLead.account_id == data.account_id,
                )
            )
            campaign = db.scalar(
                select(Campaign).where(
                    Campaign.id == data.campaign_id,
                    Campaign.organization_id == organization_id,
                )
            )
            if lead and campaign:
                RetryScheduler.process_outcome(campaign, lead, outcome.outcome_type)

        # Update account status if paid
        if outcome.outcome_type == "paid":
            account.status = "paid"
            account.outstanding_amount = Decimal("0.00")
        elif outcome.outcome_type == "dispute":
            account.status = "disputed"

        # Update call disposition if call_id provided
        if data.call_id:
            call = db.scalar(
                select(Call).where(
                    Call.id == data.call_id,
                    Call.organization_id == organization_id,
                )
            )
            if call:
                call.disposition = outcome.outcome_type.upper()
                if call.status in ("ai_talking", "customer_talking", "connected"):
                    call.status = "ended"
                    call.end_time = datetime.now(timezone.utc)

        # Log audit
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="RECORD_RECOVERY_OUTCOME",
            entity_type="RECOVERY_OUTCOME",
            entity_id=outcome.id,
            metadata_json={"outcome_type": outcome.outcome_type, "account_id": str(account.id)},
        )
        db.add(audit)
        db.commit()
        db.refresh(outcome)
        return outcome

    @classmethod
    def list_outcomes(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: Optional[uuid.UUID] = None,
        account_id: Optional[uuid.UUID] = None,
        outcome_type: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[RecoveryOutcome], int]:
        stmt = select(RecoveryOutcome).where(RecoveryOutcome.organization_id == organization_id)
        if campaign_id:
            stmt = stmt.where(RecoveryOutcome.campaign_id == campaign_id)
        if account_id:
            stmt = stmt.where(RecoveryOutcome.account_id == account_id)
        if outcome_type:
            stmt = stmt.where(RecoveryOutcome.outcome_type == outcome_type.lower())

        stmt = stmt.order_by(RecoveryOutcome.created_at.desc())
        return paginate(db, stmt, page=page, page_size=page_size)

    @classmethod
    def get_summary(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: Optional[uuid.UUID] = None,
    ) -> RecoverySummary:
        from app.db.models.promise_to_pay import PromiseToPay

        stmt = select(RecoveryOutcome.outcome_type, func.count(RecoveryOutcome.id)).where(
            RecoveryOutcome.organization_id == organization_id
        )
        if campaign_id:
            stmt = stmt.where(RecoveryOutcome.campaign_id == campaign_id)
        stmt = stmt.group_by(RecoveryOutcome.outcome_type)
        counts = dict(db.execute(stmt).all())

        ptp_count = counts.get("ptp", 0)
        paid_count = counts.get("paid", 0)
        dispute_count = counts.get("dispute", 0)
        callback_count = counts.get("callback_requested", 0)
        escalated_count = counts.get("escalated", 0)
        unreachable_count = counts.get("unreachable", 0)
        total_calls = sum(counts.values())

        other_count = total_calls - (
            ptp_count + paid_count + dispute_count + callback_count + escalated_count + unreachable_count
        )

        # Sum ptp amount
        ptp_stmt = select(func.coalesce(func.sum(PromiseToPay.amount), Decimal("0.00"))).where(
            PromiseToPay.organization_id == organization_id
        )
        total_ptp_amount = db.scalar(ptp_stmt) or Decimal("0.00")

        conversion_rate = (
            float((ptp_count + paid_count) / total_calls * 100) if total_calls > 0 else 0.0
        )

        return RecoverySummary(
            total_calls=total_calls,
            ptp_count=ptp_count,
            paid_count=paid_count,
            dispute_count=dispute_count,
            callback_count=callback_count,
            escalated_count=escalated_count,
            unreachable_count=unreachable_count,
            other_count=other_count,
            total_ptp_amount=str(total_ptp_amount),
            conversion_rate=round(conversion_rate, 2),
        )
