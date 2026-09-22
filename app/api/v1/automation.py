import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user, require_role
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.automation import (
    AutomationExecutionResponse,
    FollowUpJobResponse,
    FollowUpRuleCreate,
    FollowUpRuleResponse,
    FollowUpRuleUpdate,
)
from app.schemas.common import PaginatedResponse, SingleResponse
from app.services.recovery.automation import FollowUpEngine

router = APIRouter(prefix="/automation", tags=["Recovery Automation Rules"])


@router.post("/rules", response_model=SingleResponse[FollowUpRuleResponse], status_code=status.HTTP_201_CREATED)
def create_rule(
    data: FollowUpRuleCreate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Create a new event-driven follow-up automation rule."""
    rule = FollowUpEngine.create_rule(
        db=db,
        organization_id=current_user.organization_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=FollowUpRuleResponse.model_validate(rule))


@router.patch("/rules/{rule_id}", response_model=SingleResponse[FollowUpRuleResponse])
def update_rule(
    rule_id: uuid.UUID,
    data: FollowUpRuleUpdate,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Update a follow-up rule."""
    rule = FollowUpEngine.update_rule(
        db=db,
        organization_id=current_user.organization_id,
        rule_id=rule_id,
        data=data,
        user_id=current_user.id,
    )
    return SingleResponse(data=FollowUpRuleResponse.model_validate(rule))


@router.get("/rules/{rule_id}", response_model=SingleResponse[FollowUpRuleResponse])
def get_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve details of a specific follow-up rule."""
    rule = FollowUpEngine.get_rule(
        db=db,
        organization_id=current_user.organization_id,
        rule_id=rule_id,
    )
    return SingleResponse(data=FollowUpRuleResponse.model_validate(rule))


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Delete a follow-up rule."""
    FollowUpEngine.delete_rule(
        db=db,
        organization_id=current_user.organization_id,
        rule_id=rule_id,
        user_id=current_user.id,
    )
    return None


@router.post("/rules/{rule_id}/enable", response_model=SingleResponse[FollowUpRuleResponse])
def enable_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Enable a follow-up rule."""
    rule = FollowUpEngine.set_rule_active(
        db=db,
        organization_id=current_user.organization_id,
        rule_id=rule_id,
        is_active=True,
        user_id=current_user.id,
    )
    return SingleResponse(data=FollowUpRuleResponse.model_validate(rule))


@router.post("/rules/{rule_id}/disable", response_model=SingleResponse[FollowUpRuleResponse])
def disable_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(require_role("SUPERVISOR", "AI_MANAGER")),
    db: Session = Depends(get_db),
):
    """Disable a follow-up rule."""
    rule = FollowUpEngine.set_rule_active(
        db=db,
        organization_id=current_user.organization_id,
        rule_id=rule_id,
        is_active=False,
        user_id=current_user.id,
    )
    return SingleResponse(data=FollowUpRuleResponse.model_validate(rule))


@router.get("/rules", response_model=PaginatedResponse[FollowUpRuleResponse])
def list_rules(
    is_active: Optional[bool] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List automation rules."""
    items, total = FollowUpEngine.list_rules(
        db=db,
        organization_id=current_user.organization_id,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[FollowUpRuleResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/executions", response_model=PaginatedResponse[AutomationExecutionResponse])
def list_executions(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List rule executions with status filtering."""
    items, total = FollowUpEngine.list_executions(
        db=db,
        organization_id=current_user.organization_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[AutomationExecutionResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/jobs", response_model=PaginatedResponse[FollowUpJobResponse])
def list_jobs(
    status_filter: Optional[str] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List scheduled and dispatched communication jobs."""
    items, total = FollowUpEngine.list_jobs(
        db=db,
        organization_id=current_user.organization_id,
        status=status_filter,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        items=[FollowUpJobResponse.model_validate(i) for i in items],
        page=page,
        page_size=page_size,
        total=total,
    )


rules_alias_router = APIRouter(prefix="/automation-rules", tags=["Recovery Automation Rules Alias"])
rules_alias_router.add_api_route("", create_rule, methods=["POST"], response_model=SingleResponse[FollowUpRuleResponse], status_code=status.HTTP_201_CREATED)
rules_alias_router.add_api_route("", list_rules, methods=["GET"], response_model=PaginatedResponse[FollowUpRuleResponse])
rules_alias_router.add_api_route("/executions", list_executions, methods=["GET"], response_model=PaginatedResponse[AutomationExecutionResponse])
rules_alias_router.add_api_route("/{rule_id}", get_rule, methods=["GET"], response_model=SingleResponse[FollowUpRuleResponse])
rules_alias_router.add_api_route("/{rule_id}", update_rule, methods=["PATCH"], response_model=SingleResponse[FollowUpRuleResponse])
rules_alias_router.add_api_route("/{rule_id}", delete_rule, methods=["DELETE"], status_code=status.HTTP_204_NO_CONTENT)
rules_alias_router.add_api_route("/{rule_id}/enable", enable_rule, methods=["POST"], response_model=SingleResponse[FollowUpRuleResponse])
rules_alias_router.add_api_route("/{rule_id}/disable", disable_rule, methods=["POST"], response_model=SingleResponse[FollowUpRuleResponse])
