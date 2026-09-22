from typing import Optional
import uuid

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import ValidationException
from app.db.models.user import User
from app.schemas.ai_agent import (
    AiAgentCreate,
    AiAgentOut,
    AiAgentUpdate,
    VoicePreviewRequest,
    VoicePreviewResponse,
    VoiceProfileOut,
)
from app.schemas.common import PaginatedResponse, SingleResponse
from app.services.ai_agents import AiAgentService
from app.services.voice import VoiceService

router = APIRouter(prefix="/ai-agents", tags=["AI Agents"])


@router.post("", response_model=SingleResponse[AiAgentOut], status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AiAgentCreate,
    current_user: User = Depends(require_role("AI_MANAGER", "ORG_ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
):
    agent = AiAgentService.create_agent(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        payload=payload,
    )
    return SingleResponse(data=agent)


@router.get("", response_model=PaginatedResponse[AiAgentOut])
def list_agents(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    items, total = AiAgentService.list_agents(
        db=db,
        organization_id=current_user.organization_id,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(items=items, page=page, page_size=page_size, total=total)


@router.get("/{agent_id}", response_model=SingleResponse[AiAgentOut])
def get_agent(
    agent_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    agent = AiAgentService.get_agent(db=db, organization_id=current_user.organization_id, agent_id=agent_id)
    return SingleResponse(data=agent)


@router.patch("/{agent_id}", response_model=SingleResponse[AiAgentOut])
def update_agent(
    agent_id: uuid.UUID,
    payload: AiAgentUpdate,
    current_user: User = Depends(require_role("AI_MANAGER", "ORG_ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
):
    agent = AiAgentService.update_agent(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        agent_id=agent_id,
        payload=payload,
    )
    return SingleResponse(data=agent)


@router.post("/{agent_id}/voice", response_model=SingleResponse[VoiceProfileOut], status_code=status.HTTP_201_CREATED)
async def upload_voice_profile(
    agent_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(require_role("AI_MANAGER", "ORG_ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if not content:
        raise ValidationException("Audio file is empty.")

    profile = VoiceService.upload_voice_profile(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        agent_id=agent_id,
        filename=file.filename or "sample.wav",
        content=content,
    )
    return SingleResponse(data=profile)


@router.delete("/{agent_id}/voice", status_code=status.HTTP_204_NO_CONTENT)
def delete_voice_profile(
    agent_id: uuid.UUID,
    current_user: User = Depends(require_role("AI_MANAGER", "ORG_ADMIN", "SUPERVISOR")),
    db: Session = Depends(get_db),
):
    VoiceService.delete_voice_profile(
        db=db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        agent_id=agent_id,
    )


@router.post("/{agent_id}/voice/preview", response_model=SingleResponse[VoicePreviewResponse])
async def generate_voice_preview(
    agent_id: uuid.UUID,
    payload: VoicePreviewRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    preview = await VoiceService.generate_preview(
        db=db,
        organization_id=current_user.organization_id,
        agent_id=agent_id,
        text=payload.text,
    )
    return SingleResponse(data=preview)
