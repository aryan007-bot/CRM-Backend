import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class ExportJobCreate(BaseModel):
    export_type: str = Field(..., max_length=100)
    # ptp, disputes, campaign_summary, dial_queue, call_outcomes, audits
    file_format: str = Field(default="csv", max_length=20)
    # csv, xlsx
    filters: Optional[Dict[str, Any]] = None


class ExportJobResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    requested_by: Optional[uuid.UUID] = None
    export_type: str
    file_format: str
    filters: Optional[Dict[str, Any]] = None
    status: str
    file_size_bytes: Optional[int] = None
    error_message: Optional[str] = None
    completed_at: Optional[datetime] = None
    download_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ExportPreviewResponse(BaseModel):
    export_type: str
    filters: Optional[Dict[str, Any]] = None
    row_count: int
