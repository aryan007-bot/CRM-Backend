import csv
import io
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import openpyxl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import NotFoundException
from app.db.models.audit import AuditLog
from app.db.models.dial_queue import DialQueueItem
from app.db.models.dispute import Dispute
from app.db.models.export_job import ExportJob
from app.db.models.promise_to_pay import PromiseToPay
from app.db.models.recovery_outcome import RecoveryOutcome
from app.schemas.export import ExportJobCreate
from app.utils.pagination import paginate


class ExportService:
    @classmethod
    def create_export_job(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        data: ExportJobCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> ExportJob:
        job = ExportJob(
            organization_id=organization_id,
            requested_by=user_id,
            export_type=data.export_type.lower(),
            file_format=data.file_format.lower(),
            filters=data.filters or {},
            status="queued",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @classmethod
    def process_export(cls, db: Session, job_id: uuid.UUID) -> ExportJob:
        job = db.get(ExportJob, job_id)
        if not job:
            raise NotFoundException("Export job not found", code="EXPORT_JOB_NOT_FOUND")

        job.status = "processing"
        db.commit()

        try:
            headers, rows = cls._fetch_data(db, job)
            os.makedirs(settings.EXPORTS_STORAGE_PATH, exist_ok=True)
            filename = f"export_{job.export_type}_{job.id}.{job.file_format}"
            filepath = os.path.join(settings.EXPORTS_STORAGE_PATH, filename)

            if job.file_format == "xlsx":
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = job.export_type[:31]
                ws.append(headers)
                for row in rows:
                    ws.append([str(c) if isinstance(c, (uuid.UUID, Decimal, datetime)) else c for c in row])
                wb.save(filepath)
            else:
                with open(filepath, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    for row in rows:
                        writer.writerow([str(c) if isinstance(c, (uuid.UUID, Decimal, datetime)) else c for c in row])

            file_size = os.path.getsize(filepath)
            job.status = "completed"
            job.file_path = filepath
            job.file_size_bytes = file_size
            job.completed_at = datetime.now(timezone.utc)
        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(job)
        return job

    @classmethod
    def _fetch_data(cls, db: Session, job: ExportJob) -> Tuple[List[str], List[List[Any]]]:
        org_id = job.organization_id
        if job.export_type == "ptp":
            headers = ["ID", "Customer ID", "Account ID", "Amount", "Promised Date", "Status", "Grace Period Days"]
            items = db.scalars(select(PromiseToPay).where(PromiseToPay.organization_id == org_id)).all()
            rows = [
                [p.id, p.customer_id, p.account_id, p.amount, p.promised_date.isoformat(), p.status, p.grace_period_days]
                for p in items
            ]
            return headers, rows

        elif job.export_type == "disputes":
            headers = ["ID", "Customer ID", "Account ID", "Category", "Status", "Details", "Created At"]
            items = db.scalars(select(Dispute).where(Dispute.organization_id == org_id)).all()
            rows = [
                [d.id, d.customer_id, d.account_id, d.reason_category, d.status, d.dispute_details, d.created_at.isoformat()]
                for d in items
            ]
            return headers, rows

        elif job.export_type == "call_outcomes":
            headers = ["ID", "Call ID", "Customer ID", "Account ID", "Outcome Type", "Recorded By", "Created At"]
            items = db.scalars(select(RecoveryOutcome).where(RecoveryOutcome.organization_id == org_id)).all()
            rows = [
                [o.id, o.call_id, o.customer_id, o.account_id, o.outcome_type, o.recorded_by, o.created_at.isoformat()]
                for o in items
            ]
            return headers, rows

        elif job.export_type == "dial_queue":
            headers = ["ID", "Campaign ID", "Phone Number", "Status", "Priority", "Retry Count"]
            items = db.scalars(select(DialQueueItem).where(DialQueueItem.organization_id == org_id)).all()
            rows = [
                [q.id, q.campaign_id, q.phone_number, q.status, q.priority, q.retry_count]
                for q in items
            ]
            return headers, rows

        elif job.export_type == "audits":
            headers = ["ID", "User ID", "Action", "Entity Type", "Entity ID", "Created At"]
            items = db.scalars(select(AuditLog).where(AuditLog.organization_id == org_id)).all()
            rows = [
                [a.id, a.user_id, a.action, a.entity_type, a.entity_id, a.created_at.isoformat()]
                for a in items
            ]
            return headers, rows

        else:
            headers = ["ID", "Type", "Status"]
            rows = []
            return headers, rows

    @classmethod
    def get_export_job(cls, db: Session, organization_id: uuid.UUID, job_id: uuid.UUID) -> ExportJob:
        stmt = select(ExportJob).where(
            ExportJob.id == job_id,
            ExportJob.organization_id == organization_id,
        )
        job = db.scalar(stmt)
        if not job:
            raise NotFoundException("Export job not found", code="EXPORT_JOB_NOT_FOUND")
        return job

    @classmethod
    def preview_export(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        data: ExportJobCreate,
    ):
        from app.schemas.export import ExportPreviewResponse
        fake_job = ExportJob(
            organization_id=organization_id,
            export_type=data.export_type.lower(),
            file_format=data.file_format.lower(),
            filters=data.filters or {},
        )
        _, rows = cls._fetch_data(db, fake_job)
        return ExportPreviewResponse(
            export_type=data.export_type,
            filters=data.filters or {},
            row_count=len(rows),
        )

    @classmethod
    def list_export_jobs(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[ExportJob], int]:
        stmt = select(ExportJob).where(ExportJob.organization_id == organization_id).order_by(ExportJob.created_at.desc())
        return paginate(db, stmt, page=page, page_size=page_size)
