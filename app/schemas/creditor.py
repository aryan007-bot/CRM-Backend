import uuid
from datetime import datetime

from pydantic import BaseModel


class CreditorCreate(BaseModel):
    name: str
    status: str = "active"


class CreditorOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
