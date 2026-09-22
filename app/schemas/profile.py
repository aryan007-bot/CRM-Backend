import uuid
from typing import Optional

from pydantic import BaseModel, EmailStr


class ProfileOut(BaseModel):
    id: uuid.UUID
    name: str
    email: str
    role: str
    organization_id: uuid.UUID
    organization_name: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
