import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_role
from app.core.config import settings
from app.core.errors import PayloadTooLargeException, ValidationException
from app.core.rate_limit import rate_limit
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.common import PaginatedResponse, SingleResponse
from app.schemas.import_job import (
    ColumnMappingRequest,
    ConfirmImportResponse,
    ImportDetailOut,
    ImportJobOut,
    UploadResponse,
    ValidateResponse,
)
from app.services.imports import ImportService

router = APIRouter(prefix="/imports", tags=["Imports"])

CHUNK_SIZE = 1024 * 1024


async def read_upload_within_limit(file: UploadFile) -> bytes:
    """Reads an upload while enforcing the size limit incrementally.

    Reading the whole stream first and checking its length afterwards would let a
    client force an arbitrarily large in-memory buffer, so the limit is applied
    while streaming and the connection is abandoned as soon as it is exceeded.
    """
    limit = settings.MAX_UPLOAD_SIZE_BYTES
    chunks: list[bytes] = []
    total = 0

    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise PayloadTooLargeException(
                f"File exceeds the maximum upload size of {limit // (1024 * 1024)}MB"
            )
        chunks.append(chunk)

    if total == 0:
        raise ValidationException("The uploaded file is empty.")

    return b"".join(chunks)


@router.post(
    "/upload",
    response_model=SingleResponse[UploadResponse],
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("imports:upload", settings.UPLOAD_RATE_LIMIT_PER_MINUTE))],
)
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Uploads an Excel (.xlsx) or CSV file for import processing and returns detected columns."""
    content = await read_upload_within_limit(file)
    result = ImportService.upload_file(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        filename=file.filename or "upload.csv",
        content=content,
    )
    return SingleResponse(data=result)


@router.get("", response_model=PaginatedResponse[ImportJobOut])
def list_imports(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List historical import jobs with pagination."""
    items, total = ImportService.list_imports(
        db=db,
        organization_id=current_user.organization_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[ImportJobOut.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/{import_id}", response_model=SingleResponse[ImportDetailOut])
def get_import(
    import_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve a single import job with its detected columns and mapping suggestions."""
    detail = ImportService.get_import_detail(db, current_user.organization_id, import_id)
    return SingleResponse(data=ImportDetailOut.model_validate(detail))


@router.post(
    "/{import_id}/validate",
    response_model=SingleResponse[ValidateResponse],
    dependencies=[Depends(rate_limit("imports:validate", settings.UPLOAD_RATE_LIMIT_PER_MINUTE))],
)
def validate_import(
    import_id: uuid.UUID,
    data: ColumnMappingRequest,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Validate column mappings and file data rows against normalization and duplicate rules."""
    result = ImportService.validate_import(
        db=db,
        organization_id=current_user.organization_id,
        import_id=import_id,
        mapping=data.mapping,
    )
    return SingleResponse(data=result)


@router.post(
    "/{import_id}/confirm",
    response_model=SingleResponse[ConfirmImportResponse],
    dependencies=[Depends(rate_limit("imports:confirm", settings.UPLOAD_RATE_LIMIT_PER_MINUTE))],
)
def confirm_import(
    import_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Atomically commit valid rows into Customers, Phones, Creditors, and Accounts."""
    result = ImportService.confirm_import(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        import_id=import_id,
    )
    return SingleResponse(data=result)
