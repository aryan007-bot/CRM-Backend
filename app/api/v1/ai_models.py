import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import NotFoundException
from app.db.models.ai_infra import AiModel, AiProvider
from app.db.models.user import User
from app.schemas.control_plane.ai import (
    AiModelCreate,
    AiModelResponse,
    AiModelUpdate,
)

router = APIRouter(prefix="/ai/models", tags=["AI Model Registry"])


@router.get("", response_model=List[AiModelResponse])
def list_ai_models(
    provider_id: Optional[uuid.UUID] = None,
    model_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(AiModel)
    if provider_id:
        query = query.where(AiModel.provider_id == provider_id)
    if model_type:
        query = query.where(AiModel.model_type == model_type)

    models = db.scalars(query).all()
    return [AiModelResponse.model_validate(m) for m in models]


@router.post("", response_model=AiModelResponse, status_code=201)
def create_ai_model(
    payload: AiModelCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "AI_MANAGER")),
):
    provider = db.scalar(select(AiProvider).where(AiProvider.id == payload.provider_id))
    if not provider:
        raise NotFoundException(f"Provider {payload.provider_id} not found", code="PROVIDER_NOT_FOUND")

    model = AiModel(
        provider_id=payload.provider_id,
        name=payload.name,
        model_type=payload.model_type,
        streaming_supported=payload.streaming_supported,
        tool_support=payload.tool_support,
        context_limit=payload.context_limit,
        metadata_safe=payload.metadata_safe or {},
        enabled=True,
        status="HEALTHY",
    )
    db.add(model)
    db.commit()
    return AiModelResponse.model_validate(model)


@router.get("/{id}", response_model=AiModelResponse)
def get_ai_model(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    model = db.scalar(select(AiModel).where(AiModel.id == id))
    if not model:
        raise NotFoundException(f"AI Model {id} not found", code="MODEL_NOT_FOUND")
    return AiModelResponse.model_validate(model)


@router.patch("/{id}", response_model=AiModelResponse)
def update_ai_model(
    id: uuid.UUID,
    payload: AiModelUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "AI_MANAGER")),
):
    model = db.scalar(select(AiModel).where(AiModel.id == id))
    if not model:
        raise NotFoundException(f"AI Model {id} not found", code="MODEL_NOT_FOUND")

    if payload.name is not None:
        model.name = payload.name
    if payload.enabled is not None:
        model.enabled = payload.enabled
    if payload.status is not None:
        model.status = payload.status
    if payload.streaming_supported is not None:
        model.streaming_supported = payload.streaming_supported
    if payload.tool_support is not None:
        model.tool_support = payload.tool_support
    if payload.context_limit is not None:
        model.context_limit = payload.context_limit
    if payload.metadata_safe is not None:
        model.metadata_safe = payload.metadata_safe

    db.commit()
    return AiModelResponse.model_validate(model)

