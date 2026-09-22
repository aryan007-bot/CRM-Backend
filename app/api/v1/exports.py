import os
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.core.errors import NotFoundException
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse, SingleResponse
from app.schemas.export import ExportJobCreate, ExportJobResponse, ExportPreviewResponse
from app.services.recovery.exports import ExportService
from app.workers.export_worker import run_export_job_sync

router = APIRouter(prefix="/exports", tags=["Recovery Exports"])


def _to_export_out(job) -> ExportJobResponse:
    return ExportJobResponse(
        id=job.id,
        organization_id=job.organization_id,
        requested_by=job.requested_by,
        export_type=job.export_type,
        file_format=job.file_format,
        filters=job.filters,
        status=job.status,
        file_size_bytes=job.file_size_bytes,
        error_message=job.error_message,
        completed_at=job.completed_at,
        download_url=f"/api/v1/exports/{job.id}/download" if job.status == "completed" else None,
        created_at=job.created_at,
    )


@router.post("/preview", response_model=SingleResponse[ExportPreviewResponse])
def preview_export(
    data: ExportJobCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Preview row count for an export before generating."""
    preview = ExportService.preview_export(
        db=db,
        organization_id=current_user.organization_id,
        data=data,
    )
    return SingleResponse(data=preview)


@router.post("", response_model=SingleResponse[ExportJobResponse], status_code=status.HTTP_201_CREATED)
def create_export_job(
    data: ExportJobCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trigger background generation of CSV or Excel reports."""
    job = ExportService.create_export_job(
        db=db,
        organization_id=current_user.organization_id,
        data=data,
        user_id=current_user.id,
    )
    background_tasks.add_task(run_export_job_sync, job.id)
    return SingleResponse(data=_to_export_out(job))


@router.get("/{job_id}", response_model=SingleResponse[ExportJobResponse])
def get_export_job(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Check export generation status."""
    job = ExportService.get_export_job(
        db=db,
        organization_id=current_user.organization_id,
        job_id=job_id,
    )
    return SingleResponse(data=_to_export_out(job))


@router.get("/{job_id}/download")
def download_export_file(
    job_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download the completed export file."""
    job = ExportService.get_export_job(
        db=db,
        organization_id=current_user.organization_id,
        job_id=job_id,
    )
    if job.status != "completed" or not job.file_path or not os.path.exists(job.file_path):
        raise NotFoundException("Export file is not ready or has expired", code="FILE_NOT_FOUND")

    media_type = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if job.file_format == "xlsx"
        else "text/csv"
    )
    filename = os.path.basename(job.file_path)
    return FileResponse(path=job.file_path, media_type=media_type, filename=filename)


@router.get("", response_model=PaginatedResponse[ExportJobResponse])
def list_export_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List export history."""
    items, total = ExportService.list_export_jobs(
        db=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[_to_export_out(j) for j in items],
        page=page,
        page_size=page_size,
        total=total,
    )
