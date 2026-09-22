import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.db import session as db_session
from app.services.recovery.queue import DialQueueService


def process_queue_batch_sync(
    organization_id: uuid.UUID,
    worker_id: str,
    batch_size: int = 5,
    campaign_id: Optional[uuid.UUID] = None,
) -> int:
    db: Session = db_session.SessionLocal()
    try:
        items = DialQueueService.reserve_next_batch(
            db=db,
            organization_id=organization_id,
            worker_id=worker_id,
            batch_size=batch_size,
            campaign_id=campaign_id,
        )
        return len(items)
    finally:
        db.close()
