import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.queue import QueueMetricSnapshot, QueueRegistryItem
from app.services.control_plane.queue_service import QueueService


def test_ensure_default_queues(db: Session):
    QueueService.ensure_default_queues(db)
    queues = db.scalars(select(QueueRegistryItem)).all()
    assert len(queues) >= 4
    types = [q.queue_type for q in queues]
    assert "DIAL" in types
    assert "ANALYSIS" in types
    assert "FOLLOW_UP" in types
    assert "EXPORT" in types


def test_queue_pause_and_resume(db: Session):
    QueueService.ensure_default_queues(db)
    queue = db.scalars(select(QueueRegistryItem)).first()
    assert queue is not None

    # Pause queue
    paused = QueueService.pause_queue(db, queue.id)
    assert paused.status == "PAUSED"

    # Resume queue
    resumed = QueueService.resume_queue(db, queue.id)
    assert resumed.status == "HEALTHY"


def test_capture_metrics_snapshot(db: Session):
    QueueService.ensure_default_queues(db)
    queue = db.scalars(select(QueueRegistryItem)).first()

    snapshot = QueueService.capture_metrics_snapshot(db, queue.id)
    assert snapshot.queue_id == queue.id
    assert snapshot.pending >= 0
    assert snapshot.worker_count >= 1
