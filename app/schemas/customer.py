import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr


class CustomerPhoneBase(BaseModel):
    phone: str
    phone_type: str = "mobile"
    is_primary: bool = False


class CustomerPhoneCreate(CustomerPhoneBase):
    pass


class CustomerPhoneOut(CustomerPhoneBase):
    id: uuid.UUID
    normalized_phone: str
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerCreate(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    status: str = "active"
    phones: Optional[List[CustomerPhoneCreate]] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    status: Optional[str] = None


class CustomerOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    email: Optional[str] = None
    status: str
    phones: List[CustomerPhoneOut] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
