import uuid
from datetime import datetime, time, timezone

from app.db.models.campaign import Campaign, CampaignLead
from app.services.recovery.retry import RetryScheduler


def test_retry_scheduler_terminal_paid():
    campaign = Campaign(max_attempts=3, retry_delay_minutes=60)
    lead = CampaignLead(campaign_id=uuid.uuid4(), account_id=uuid.uuid4(), attempt_count=0)

    should_retry, next_time = RetryScheduler.process_outcome(campaign, lead, "paid")
    assert should_retry is False
    assert next_time is None
    assert lead.contact_state == "resolved"
    assert lead.status == "completed"
    assert lead.attempt_count == 1


def test_retry_scheduler_terminal_ptp():
    campaign = Campaign(max_attempts=3, retry_delay_minutes=60)
    lead = CampaignLead(campaign_id=uuid.uuid4(), account_id=uuid.uuid4(), attempt_count=0)

    should_retry, next_time = RetryScheduler.process_outcome(campaign, lead, "ptp")
    assert should_retry is False
    assert next_time is None
    assert lead.contact_state == "promised"
    assert lead.status == "completed"


def test_retry_scheduler_non_terminal_exponential_backoff():
    campaign = Campaign(max_attempts=3, retry_delay_minutes=30)
    lead = CampaignLead(campaign_id=uuid.uuid4(), account_id=uuid.uuid4(), attempt_count=0)
    now = datetime(2026, 9, 22, 10, 0, tzinfo=timezone.utc)

    # First attempt fails (unreachable) -> backoff factor 2^0 = 1 -> delay 30m
    should_retry, next_time = RetryScheduler.process_outcome(campaign, lead, "unreachable", at_time=now)
    assert should_retry is True
    assert lead.attempt_count == 1
    assert lead.status == "retry"
    assert next_time == datetime(2026, 9, 22, 10, 30, tzinfo=timezone.utc)

    # Second attempt fails (unreachable) -> backoff factor 2^1 = 2 -> delay 60m
    second_time = datetime(2026, 9, 22, 11, 0, tzinfo=timezone.utc)
    should_retry, next_time = RetryScheduler.process_outcome(campaign, lead, "unreachable", at_time=second_time)
    assert should_retry is True
    assert lead.attempt_count == 2
    assert next_time == datetime(2026, 9, 22, 12, 0, tzinfo=timezone.utc)

    # Third attempt fails -> reaches max_attempts (3) -> terminal failed!
    third_time = datetime(2026, 9, 22, 13, 0, tzinfo=timezone.utc)
    should_retry, next_time = RetryScheduler.process_outcome(campaign, lead, "unreachable", at_time=third_time)
    assert should_retry is False
    assert next_time is None
    assert lead.attempt_count == 3
    assert lead.status == "failed"
