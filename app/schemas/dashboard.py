from decimal import Decimal

from pydantic import BaseModel


class DashboardSummaryOut(BaseModel):
    customers: int
    accounts: int
    total_outstanding: Decimal
    active_campaigns: int
    pending_imports: int
