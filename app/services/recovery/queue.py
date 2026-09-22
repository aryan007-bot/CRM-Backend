import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException
from app.db.models.campaign import Campaign, CampaignLead
from app.db.models.campaign_run import CampaignRun
from app.db.models.dial_queue import DialQueueItem
from app.utils.pagination import paginate


class DialQueueService:
    @classmethod
    def enqueue_lead(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: uuid.UUID,
        lead: CampaignLead,
        phone_number: str,
        campaign_run_id: Optional[uuid.UUID] = None,
        priority: int = 1,
        scheduled_for: Optional[datetime] = None,
    ) -> DialQueueItem:
        account = lead.account
        customer_id = account.customer_id if account else lead.account_id

        queue_item = DialQueueItem(
            organization_id=organization_id,
            campaign_id=campaign_id,
            campaign_run_id=campaign_run_id,
            lead_id=lead.id,
            customer_id=customer_id,
            account_id=lead.account_id,
            phone_number=phone_number,
            priority=priority,
            status="pending",
            retry_count=lead.attempt_count,
            max_retries=3,
            scheduled_for=scheduled_for,
        )
        db.add(queue_item)
        lead.status = "queued"
        return queue_item

    @classmethod
    def reserve_next_batch(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        worker_id: str,
        batch_size: int = 1,
        campaign_id: Optional[uuid.UUID] = None,
    ) -> List[DialQueueItem]:
        now = datetime.now(timezone.utc)
        stmt = select(DialQueueItem).where(
            DialQueueItem.organization_id == organization_id,
            DialQueueItem.status == "pending",
            (DialQueueItem.scheduled_for.is_(None)) | (DialQueueItem.scheduled_for <= now),
        )

        if campaign_id:
            stmt = stmt.where(DialQueueItem.campaign_id == campaign_id)

        stmt = stmt.order_by(
            DialQueueItem.priority.desc(),
            DialQueueItem.created_at.asc(),
        ).limit(batch_size)

        dialect_name = db.bind.dialect.name if db.bind else ""
        if dialect_name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        items = db.scalars(stmt).all()
        if not items:
            return []

        for item in items:
            item.status = "reserved"
            item.reserved_by = worker_id
            item.reserved_at = now

        db.commit()
        for item in items:
            db.refresh(item)

        return items

    @classmethod
    def release_reservation(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
    ) -> DialQueueItem:
        stmt = select(DialQueueItem).where(
            DialQueueItem.id == item_id,
            DialQueueItem.organization_id == organization_id,
        )
        item = db.scalar(stmt)
        if not item:
            raise NotFoundException("Queue item not found", code="QUEUE_ITEM_NOT_FOUND")

        item.status = "pending"
        item.reserved_by = None
        item.reserved_at = None
        db.commit()
        db.refresh(item)
        return item

    @classmethod
    def complete_item(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        item_id: uuid.UUID,
        status: str = "completed",
    ) -> DialQueueItem:
        stmt = select(DialQueueItem).where(
            DialQueueItem.id == item_id,
            DialQueueItem.organization_id == organization_id,
        )
        item = db.scalar(stmt)
        if not item:
            raise NotFoundException("Queue item not found", code="QUEUE_ITEM_NOT_FOUND")

        item.status = status
        db.commit()
        db.refresh(item)
        return item

    @classmethod
    def list_queue_items(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        campaign_id: Optional[uuid.UUID] = None,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[DialQueueItem], int]:
        stmt = select(DialQueueItem).where(DialQueueItem.organization_id == organization_id)
        if campaign_id:
            stmt = stmt.where(DialQueueItem.campaign_id == campaign_id)
        if status:
            stmt = stmt.where(DialQueueItem.status == status)

        stmt = stmt.order_by(DialQueueItem.priority.desc(), DialQueueItem.created_at.desc())
        return paginate(db, stmt, page=page, page_size=page_size)

    @classmethod
    def bulk_action(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        item_ids: List[uuid.UUID],
        action: str,
    ) -> int:
        target_status = "paused" if action == "pause" else "pending" if action == "resume" else "cancelled"
        from sqlalchemy import update
        stmt = (
            update(DialQueueItem)
            .where(
                DialQueueItem.id.in_(item_ids),
                DialQueueItem.organization_id == organization_id,
            )
            .values(status=target_status)
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount
