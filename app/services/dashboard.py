import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.account import Account
from app.db.models.campaign import Campaign
from app.db.models.customer import Customer
from app.db.models.import_job import Import
from app.schemas.dashboard import DashboardSummaryOut


class DashboardService:
    @staticmethod
    def get_summary(db: Session, organization_id: uuid.UUID) -> DashboardSummaryOut:
        # Real counts scoped to organization
        customer_count = db.scalar(
            select(func.count(Customer.id)).where(Customer.organization_id == organization_id)
        ) or 0

        account_count = db.scalar(
            select(func.count(Account.id)).where(Account.organization_id == organization_id)
        ) or 0

        total_outstanding = db.scalar(
            select(func.coalesce(func.sum(Account.outstanding_amount), Decimal("0.00"))).where(
                Account.organization_id == organization_id
            )
        ) or Decimal("0.00")

        active_campaigns = db.scalar(
            select(func.count(Campaign.id)).where(
                Campaign.organization_id == organization_id,
                Campaign.status.in_(["ready", "running"]),
            )
        ) or 0

        pending_imports = db.scalar(
            select(func.count(Import.id)).where(
                Import.organization_id == organization_id,
                Import.status.in_(["uploaded", "processing"]),
            )
        ) or 0

        return DashboardSummaryOut(
            customers=customer_count,
            accounts=account_count,
            total_outstanding=total_outstanding,
            active_campaigns=active_campaigns,
            pending_imports=pending_imports,
        )
