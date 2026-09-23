import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, get_db, require_role
from app.core.errors import NotFoundException
from app.db.models.ai_infra import AiProvider, AiRoutingRule
from app.db.models.audit import AuditLog
from app.db.models.user import User
from app.schemas.control_plane.ai import (
    AiRoutingRuleCreate,
    AiRoutingRuleResponse,
    AiRoutingRuleUpdate,
)

router = APIRouter(prefix="/ai/routing", tags=["AI Routing"])


@router.get("", response_model=List[AiRoutingRuleResponse])
def list_routing_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(AiRoutingRule)
    if "SUPER_ADMIN" not in current_user.roles:
        query = query.where(
            (AiRoutingRule.organization_id == current_user.organization_id)
            | (AiRoutingRule.scope == "PLATFORM")
        )

    rules = db.scalars(query.order_by(AiRoutingRule.priority.asc())).all()
    return [AiRoutingRuleResponse.model_validate(r) for r in rules]


@router.post("", response_model=AiRoutingRuleResponse, status_code=status.HTTP_201_CREATED)
def create_routing_rule(
    payload: AiRoutingRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "AI_MANAGER")),
):
    provider = db.scalar(select(AiProvider).where(AiProvider.id == payload.primary_provider_id))
    if not provider:
        raise NotFoundException(f"Provider {payload.primary_provider_id} not found", code="PROVIDER_NOT_FOUND")

    rule = AiRoutingRule(
        scope=payload.scope,
        organization_id=payload.organization_id,
        service_type=payload.service_type,
        primary_provider_id=payload.primary_provider_id,
        primary_model_id=payload.primary_model_id,
        fallbacks=payload.fallbacks or [],
        enabled=payload.enabled,
        priority=payload.priority,
        conditions=payload.conditions or [],
    )
    db.add(rule)
    db.flush()

    audit = AuditLog(
        organization_id=payload.organization_id or uuid.UUID("00000000-0000-0000-0000-000000000000"),
        user_id=current_user.id,
        action="AI_ROUTING_RULE_CREATED",
        entity_type="ai_routing_rule",
        entity_id=rule.id,
        metadata_json={"service_type": rule.service_type, "primary_provider_id": str(rule.primary_provider_id)},
    )
    db.add(audit)
    db.commit()

    return AiRoutingRuleResponse.model_validate(rule)


@router.patch("/{id}", response_model=AiRoutingRuleResponse)
def update_routing_rule(
    id: uuid.UUID,
    payload: AiRoutingRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "AI_MANAGER")),
):
    rule = db.scalar(select(AiRoutingRule).where(AiRoutingRule.id == id))
    if not rule:
        raise NotFoundException(f"Routing rule {id} not found", code="ROUTING_RULE_NOT_FOUND")

    if payload.primary_provider_id is not None:
        rule.primary_provider_id = payload.primary_provider_id
    if payload.primary_model_id is not None:
        rule.primary_model_id = payload.primary_model_id
    if payload.fallbacks is not None:
        rule.fallbacks = payload.fallbacks
    if payload.enabled is not None:
        rule.enabled = payload.enabled
    if payload.priority is not None:
        rule.priority = payload.priority
    if payload.conditions is not None:
        rule.conditions = payload.conditions

    db.commit()
    return AiRoutingRuleResponse.model_validate(rule)



@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routing_rule(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "AI_MANAGER")),
):
    rule = db.scalar(select(AiRoutingRule).where(AiRoutingRule.id == id))
    if not rule:
        raise NotFoundException(f"Routing rule {id} not found", code="ROUTING_RULE_NOT_FOUND")

    db.delete(rule)
    db.flush()
    return None


@router.post("/rules", response_model=AiRoutingRuleResponse, status_code=status.HTTP_201_CREATED)
def create_routing_rule_alias(
    payload: AiRoutingRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "AI_MANAGER")),
):
    return create_routing_rule(payload=payload, db=db, current_user=current_user)


@router.patch("/rules/{id}", response_model=AiRoutingRuleResponse)
def update_routing_rule_alias(
    id: uuid.UUID,
    payload: AiRoutingRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "AI_MANAGER")),
):
    return update_routing_rule(id=id, payload=payload, db=db, current_user=current_user)


@router.delete("/rules/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_routing_rule_alias(
    id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("SUPER_ADMIN", "AI_MANAGER")),
):
    return delete_routing_rule(id=id, db=db, current_user=current_user)

