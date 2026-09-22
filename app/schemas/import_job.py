import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class UploadResponse(BaseModel):
    import_id: uuid.UUID
    filename: str
    file_type: str
    detected_columns: List[str]
    row_count: int
    # Server-side column suggestions so the client does not re-implement the
    # alias heuristics; keys are standard fields, values may be null.
    suggested_mapping: Dict[str, Optional[str]] = {}


class ColumnMappingRequest(BaseModel):
    mapping: Dict[str, str]
    # e.g. {"customer_name": "Name", "phone": "Phone Number", "account_number": "Account", "outstanding_amount": "Amount", "due_date": "Due Date", "creditor_name": "Creditor"}


class ValidationErrorItem(BaseModel):
    row: int
    field: str
    code: str
    message: str


class ValidateSummary(BaseModel):
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int


class ValidateResponse(BaseModel):
    summary: ValidateSummary
    warnings: List[str] = []
    errors: List[ValidationErrorItem] = []
    preview: List[Dict[str, Any]] = []


class ConfirmImportResponse(BaseModel):
    import_id: uuid.UUID
    status: str
    imported_rows: int
    total_rows: int


class ImportJobOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    filename: str
    file_type: str
    status: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    duplicate_rows: int
    imported_rows: int
    created_by: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ImportDetailOut(ImportJobOut):
    """Single-import view.

    Includes the columns detected in the uploaded file and the server's mapping
    suggestions, so the mapping screen can be reloaded or bookmarked instead of
    depending on state carried over from the upload response.
    """

    detected_columns: List[str] = []
    suggested_mapping: Dict[str, Optional[str]] = {}
