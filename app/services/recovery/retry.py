from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from app.db.models.campaign import Campaign, CampaignLead


class RetryScheduler:
    TERMINAL_OUTCOMES = {
        "paid": ("resolved", "completed"),
        "ptp": ("promised", "completed"),
        "dispute": ("disputed", "completed"),
        "dnc": ("dnc", "skipped"),
        "wrong_party": ("unreachable", "failed"),
    }

    @classmethod
    def process_outcome(
        cls,
        campaign: Campaign,
        lead: CampaignLead,
        outcome_type: str,
        at_time: Optional[datetime] = None,
    ) -> Tuple[bool, Optional[datetime]]:
        now = at_time or datetime.now(timezone.utc)
        normalized_outcome = outcome_type.lower()

        lead.last_attempt_at = now
        lead.last_outcome = normalized_outcome
        lead.attempt_count += 1

        # 1. Check if outcome is terminal
        if normalized_outcome in cls.TERMINAL_OUTCOMES:
            contact_state, status = cls.TERMINAL_OUTCOMES[normalized_outcome]
            lead.contact_state = contact_state
            lead.status = status
            lead.next_attempt_at = None
            return False, None

        # 2. Non-terminal outcomes (e.g. unreachable, busy, no_answer, failed, refused, language_barrier)
        lead.contact_state = "unreachable" if "reach" in normalized_outcome or "answer" in normalized_outcome else "contacted"

        if lead.attempt_count >= campaign.max_attempts:
            lead.status = "failed"
            lead.next_attempt_at = None
            return False, None

        # Exponential backoff based on attempts
        backoff_factor = 2 ** max(0, lead.attempt_count - 1)
        delay_minutes = campaign.retry_delay_minutes * backoff_factor
        next_attempt = now + timedelta(minutes=delay_minutes)

        lead.status = "retry"
        lead.next_attempt_at = next_attempt
        return True, next_attempt
