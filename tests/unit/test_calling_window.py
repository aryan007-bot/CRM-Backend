import uuid
from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.db.models.campaign import Campaign
from app.services.recovery.calling_window import CallingWindowService


def test_calling_window_within_hours():
    campaign = Campaign(
        name="Test Campaign",
        timezone="Asia/Kolkata",
        calling_start_time=time(9, 0),
        calling_end_time=time(18, 0),
    )
    kolkata_tz = ZoneInfo("Asia/Kolkata")
    midday = datetime(2026, 9, 22, 12, 0, tzinfo=kolkata_tz)
    assert CallingWindowService.is_callable_now(campaign, at_time=midday) is True


def test_calling_window_outside_hours():
    campaign = Campaign(
        name="Test Campaign",
        timezone="Asia/Kolkata",
        calling_start_time=time(9, 0),
        calling_end_time=time(18, 0),
    )
    kolkata_tz = ZoneInfo("Asia/Kolkata")
    night = datetime(2026, 9, 22, 21, 30, tzinfo=kolkata_tz)
    assert CallingWindowService.is_callable_now(campaign, at_time=night) is False

    early_morning = datetime(2026, 9, 22, 7, 0, tzinfo=kolkata_tz)
    assert CallingWindowService.is_callable_now(campaign, at_time=early_morning) is False


def test_calling_window_campaign_date_boundaries():
    kolkata_tz = ZoneInfo("Asia/Kolkata")
    campaign = Campaign(
        name="Dated Campaign",
        timezone="Asia/Kolkata",
        calling_start_time=time(9, 0),
        calling_end_time=time(18, 0),
        start_at=datetime(2026, 10, 1, 0, 0, tzinfo=kolkata_tz),
        end_at=datetime(2026, 10, 31, 23, 59, tzinfo=kolkata_tz),
    )
    # Before start_at
    midday_sept = datetime(2026, 9, 22, 12, 0, tzinfo=kolkata_tz)
    assert CallingWindowService.is_callable_now(campaign, at_time=midday_sept) is False

    # Within dates and within hours
    midday_oct = datetime(2026, 10, 15, 12, 0, tzinfo=kolkata_tz)
    assert CallingWindowService.is_callable_now(campaign, at_time=midday_oct) is True

    # After end_at
    midday_nov = datetime(2026, 11, 5, 12, 0, tzinfo=kolkata_tz)
    assert CallingWindowService.is_callable_now(campaign, at_time=midday_nov) is False
