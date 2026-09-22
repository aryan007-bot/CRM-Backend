from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Tuple
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.call import Call
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.customer import Customer, CustomerPhone
from app.db.models.dnc import DncRecord
from app.services.recovery.calling_window import CallingWindowService


class LeadEligibilityService:
    TERMINAL_STATES = {"resolved", "promised", "disputed", "dnc"}

    @classmethod
    def evaluate_lead(
        cls,
        db: Session,
        campaign: Campaign,
        lead: CampaignLead,
        at_time: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        now = at_time or datetime.now(timezone.utc)

        # 1. Calling window
        if not CallingWindowService.is_callable_now(campaign, now):
            return False, "OUTSIDE_CALLING_WINDOW", None

        # 2. Account checks
        account: Optional[Account] = lead.account
        if not account:
            account = db.get(Account, lead.account_id)
        if not account:
            return False, "ACCOUNT_NOT_FOUND", None
        if account.status != "active":
            return False, f"ACCOUNT_STATUS_{account.status.upper()}", None
        if account.outstanding_amount <= Decimal("0.00"):
            return False, "NO_OUTSTANDING_BALANCE", None

        # 3. Customer checks
        customer: Optional[Customer] = account.customer
        if not customer:
            customer = db.get(Customer, account.customer_id)
        if not customer:
            return False, "CUSTOMER_NOT_FOUND", None
        if customer.status != "active":
            return False, f"CUSTOMER_STATUS_{customer.status.upper()}", None
        if customer.is_opted_out:
            return False, "CUSTOMER_OPTED_OUT", None

        # 4. Lead terminal state & attempt limits
        if lead.contact_state in cls.TERMINAL_STATES:
            return False, f"TERMINAL_STATE_{lead.contact_state.upper()}", None
        if lead.attempt_count >= campaign.max_attempts:
            return False, "MAX_ATTEMPTS_EXCEEDED", None

        # 5. Retry cooldown
        if lead.last_attempt_at:
            last_attempt = lead.last_attempt_at
            if last_attempt.tzinfo is None:
                last_attempt = last_attempt.replace(tzinfo=timezone.utc)
            now_tz = now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)
            elapsed_minutes = (now_tz - last_attempt).total_seconds() / 60
            if elapsed_minutes < campaign.retry_cooldown_minutes:
                return False, "RETRY_COOLDOWN_ACTIVE", None

        # 6. Daily attempt limit
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_calls_count = db.scalar(
            select(func.count(Call.id)).where(
                Call.account_id == account.id,
                Call.created_at >= today_start,
            )
        ) or 0
        if daily_calls_count >= campaign.daily_attempt_limit:
            return False, "DAILY_ATTEMPT_LIMIT_EXCEEDED", None

        # 7. Customer phone selection
        phones = customer.phones if hasattr(customer, "phones") and customer.phones else []
        if not phones:
            phones = db.scalars(
                select(CustomerPhone).where(CustomerPhone.customer_id == customer.id)
            ).all()

        if not phones:
            return False, "NO_PHONE_NUMBER", None

        # Prefer primary phone
        primary_phone = next((p for p in phones if p.is_primary), phones[0])
        target_phone = primary_phone.normalized_phone or primary_phone.phone

        # 8. DNC check
        if campaign.dnc_enforcement:
            dnc_exists = db.scalar(
                select(DncRecord.id).where(
                    DncRecord.organization_id == campaign.organization_id,
                    DncRecord.phone_number == target_phone,
                    DncRecord.is_active == True,
                )
            )
            if dnc_exists:
                return False, "PHONE_IN_DNC", None

        return True, None, target_phone
