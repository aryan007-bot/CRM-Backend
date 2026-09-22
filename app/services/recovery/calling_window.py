from datetime import datetime, time
from typing import Optional
from zoneinfo import ZoneInfo

from app.db.models.campaign import Campaign


class CallingWindowService:
    @staticmethod
    def get_campaign_now(campaign: Campaign, at_time: Optional[datetime] = None) -> datetime:
        try:
            tz = ZoneInfo(campaign.timezone or "Asia/Kolkata")
        except Exception:
            tz = ZoneInfo("Asia/Kolkata")

        if at_time is not None:
            if at_time.tzinfo is None:
                return at_time.replace(tzinfo=ZoneInfo("UTC")).astimezone(tz)
            return at_time.astimezone(tz)

        return datetime.now(tz)

    @classmethod
    def is_callable_now(cls, campaign: Campaign, at_time: Optional[datetime] = None) -> bool:
        local_now = cls.get_campaign_now(campaign, at_time)

        # Check campaign date boundaries if configured
        if campaign.start_at:
            start_at_local = campaign.start_at if campaign.start_at.tzinfo else campaign.start_at.replace(tzinfo=ZoneInfo("UTC"))
            if local_now < start_at_local:
                return False

        if campaign.end_at:
            end_at_local = campaign.end_at if campaign.end_at.tzinfo else campaign.end_at.replace(tzinfo=ZoneInfo("UTC"))
            if local_now > end_at_local:
                return False

        current_time = local_now.time()
        start_time = campaign.calling_start_time or time(9, 0)
        end_time = campaign.calling_end_time or time(18, 0)

        return start_time <= current_time <= end_time
