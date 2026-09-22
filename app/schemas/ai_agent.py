from datetime import datetime
from decimal import Decimal
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, Field


class VoiceProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    provider: str
    sample_rate: int
    duration_seconds: Optional[Decimal] = None
    status: str
    created_at: datetime


class AiAgentCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    language: str = Field(default="en-IN", max_length=50)
    model: str = Field(default="llama-3.3-70b-versatile", max_length=100)
    system_prompt: str = Field(..., min_length=10)
    disclosure: str = Field(..., min_length=10)


class AiAgentUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    language: Optional[str] = Field(None, max_length=50)
    model: Optional[str] = Field(None, max_length=100)
    system_prompt: Optional[str] = Field(None, min_length=10)
    disclosure: Optional[str] = Field(None, min_length=10)
    status: Optional[str] = None
    is_active: Optional[bool] = None


class AiAgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    language: str
    model: str
    system_prompt: str
    disclosure: str
    status: str
    is_active: bool
    voice_profile: Optional[VoiceProfileOut] = None
    created_at: datetime
    updated_at: datetime


class VoicePreviewRequest(BaseModel):
    text: str = Field(..., min_length=3, max_length=500)


class VoicePreviewResponse(BaseModel):
    audio_base64: str
    sample_rate: int
    duration_seconds: float
    format: str
