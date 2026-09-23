from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import JobNotRetryableException, NotFoundException
from app.db.models.audit import AuditLog
from app.db.models.system_job import SystemJob
from app.schemas.control_plane.job import JobRetryResponse
from app.services.control_plane.event_bus import event_bus


class JobService:
    """Provides a normalized job view and safe retry execution."""

    @staticmethod
    def get_job(db: Session, job_id: uuid.UUID) -> SystemJob:
        job = db.scalar(select(SystemJob).where(SystemJob.id == job_id))
        if not job:
            raise NotFoundException(f"Job {job_id} not found", code="JOB_NOT_FOUND")
        return job

    @staticmethod
    def retry_job(
        db: Session,
        job_id: uuid.UUID,
        requested_by: Optional[uuid.UUID] = None,
    ) -> JobRetryResponse:
        job = db.scalar(select(SystemJob).where(SystemJob.id == job_id))
        if not job:
            raise NotFoundException(f"Job {job_id} not found", code="JOB_NOT_FOUND")

        # Guard: Is the job running?
        if job.status == "RUNNING":
            raise JobNotRetryableException("Cannot retry an actively running job", code="JOB_NOT_RETRYABLE")

        # Guard: Has the job completed successfully?
        if job.status == "COMPLETED":
            raise JobNotRetryableException("Completed job cannot be retried", code="JOB_NOT_RETRYABLE")

        # Guard: Exceeded attempts?
        if job.attempts >= job.max_attempts:
            raise JobNotRetryableException(
                f"Job has exceeded max retry attempts ({job.max_attempts})",
                code="JOB_NOT_RETRYABLE",
            )

        now = datetime.now(timezone.utc)
        job.status = "QUEUED"
        job.attempts += 1
        job.scheduled_at = now
        job.last_error_code = None
        job.last_error_message = None

        audit = AuditLog(
            organization_id=job.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=requested_by,
            action="JOB_RETRY_REQUESTED",
            entity_type="system_job",
            entity_id=job.id,
            metadata_json={"status": "QUEUED", "attempts": job.attempts},
        )
        db.add(audit)

        event_bus.emit_operational_event(
            db=db,
            event_type="job.retried",
            scope=job.scope,
            organization_id=job.organization_id,
            entity_type="job",
            entity_id=str(job.id),
            severity="INFO",
            message=f"Job {job.id} queued for retry attempt {job.attempts}",
        )
        db.flush()

        return JobRetryResponse(
            job_id=job.id,
            status=job.status,
            attempts=job.attempts,
            message="Job queued for retry",
        )

    @staticmethod
    def cancel_job(
        db: Session,
        job_id: uuid.UUID,
        requested_by: Optional[uuid.UUID] = None,
    ) -> SystemJob:
        job = db.scalar(select(SystemJob).where(SystemJob.id == job_id))
        if not job:
            raise NotFoundException(f"Job {job_id} not found", code="JOB_NOT_FOUND")

        job.status = "CANCELLED"
        audit = AuditLog(
            organization_id=job.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=requested_by,
            action="JOB_CANCELLED",
            entity_type="system_job",
            entity_id=job.id,
            metadata_json={"status": "CANCELLED"},
        )
        db.add(audit)
        event_bus.emit_operational_event(
            db=db,
            event_type="job.cancelled",
            scope=job.scope,
            organization_id=job.organization_id,
            entity_type="job",
            entity_id=str(job.id),
            severity="WARNING",
            message=f"Job {job.id} cancelled",
        )
        db.flush()
        return job

