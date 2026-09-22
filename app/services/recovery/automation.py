import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundException
from app.db.models.audit import AuditLog
from app.db.models.automation import AutomationExecution, FollowUpJob, FollowUpRule
from app.schemas.automation import FollowUpRuleCreate, FollowUpRuleUpdate
from app.utils.pagination import paginate


class FollowUpEngine:
    @classmethod
    def create_rule(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        data: FollowUpRuleCreate,
        user_id: Optional[uuid.UUID] = None,
    ) -> FollowUpRule:
        rule = FollowUpRule(
            organization_id=organization_id,
            name=data.name.strip(),
            event_trigger=data.event_trigger,
            condition_config=data.condition_config or {},
            action_type=data.action_type,
            action_template=data.action_template,
            is_active=data.is_active,
            delay_minutes=data.delay_minutes,
        )
        db.add(rule)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE_FOLLOW_UP_RULE",
            entity_type="FOLLOW_UP_RULE",
            entity_id=rule.id,
            metadata_json={"trigger": rule.event_trigger, "action": rule.action_type},
        )
        db.add(audit)
        db.commit()
        db.refresh(rule)
        return rule

    @classmethod
    def update_rule(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        rule_id: uuid.UUID,
        data: FollowUpRuleUpdate,
        user_id: Optional[uuid.UUID] = None,
    ) -> FollowUpRule:
        stmt = select(FollowUpRule).where(
            FollowUpRule.id == rule_id,
            FollowUpRule.organization_id == organization_id,
        )
        rule = db.scalar(stmt)
        if not rule:
            raise NotFoundException("Follow-up rule not found", code="RULE_NOT_FOUND")

        if data.name is not None:
            rule.name = data.name.strip()
        if data.event_trigger is not None:
            rule.event_trigger = data.event_trigger
        if data.condition_config is not None:
            rule.condition_config = data.condition_config
        if data.action_type is not None:
            rule.action_type = data.action_type
        if data.action_template is not None:
            rule.action_template = data.action_template
        if data.is_active is not None:
            rule.is_active = data.is_active
        if data.delay_minutes is not None:
            rule.delay_minutes = data.delay_minutes

        db.commit()
        db.refresh(rule)
        return rule

    @classmethod
    def list_rules(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        is_active: Optional[bool] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[FollowUpRule], int]:
        stmt = select(FollowUpRule).where(FollowUpRule.organization_id == organization_id)
        if is_active is not None:
            stmt = stmt.where(FollowUpRule.is_active == is_active)

        stmt = stmt.order_by(FollowUpRule.created_at.desc())
        return paginate(db, stmt, page=page, page_size=page_size)

    @classmethod
    def dispatch_trigger(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        trigger_event: str,
        target_entity_type: str,
        target_entity_id: uuid.UUID,
        recipient: Optional[str] = None,
        payload: Optional[str] = None,
    ) -> List[AutomationExecution]:
        # Find active rules matching event
        rules = db.scalars(
            select(FollowUpRule).where(
                FollowUpRule.organization_id == organization_id,
                FollowUpRule.event_trigger == trigger_event,
                FollowUpRule.is_active == True,
            )
        ).all()

        executions = []
        now = datetime.now(timezone.utc)

        for rule in rules:
            # Check idempotency: if execution already exists for this rule and target
            existing = db.scalar(
                select(AutomationExecution).where(
                    AutomationExecution.rule_id == rule.id,
                    AutomationExecution.target_entity_type == target_entity_type,
                    AutomationExecution.target_entity_id == target_entity_id,
                )
            )
            if existing:
                continue

            scheduled_at = now + timedelta(minutes=rule.delay_minutes)

            execution = AutomationExecution(
                organization_id=organization_id,
                rule_id=rule.id,
                trigger_event=trigger_event,
                target_entity_type=target_entity_type,
                target_entity_id=target_entity_id,
                status="executed" if rule.delay_minutes == 0 else "pending",
                action_output=f"Dispatched {rule.action_type}",
                executed_at=now if rule.delay_minutes == 0 else None,
            )
            db.add(execution)
            db.flush()

            channel = "sms" if "sms" in rule.action_type else "whatsapp" if "whatsapp" in rule.action_type else "email"
            target_recipient = recipient or "customer_default"
            content = payload or rule.action_template or f"Follow-up for {trigger_event}"

            job = FollowUpJob(
                organization_id=organization_id,
                execution_id=execution.id,
                channel=channel,
                recipient=target_recipient,
                payload=content,
                status="sent" if rule.delay_minutes == 0 else "scheduled",
                scheduled_at=scheduled_at,
                sent_at=now if rule.delay_minutes == 0 else None,
            )
            db.add(job)
            executions.append(execution)

        db.commit()
        for e in executions:
            db.refresh(e)
        return executions

    @classmethod
    def list_executions(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[AutomationExecution], int]:
        stmt = select(AutomationExecution).where(AutomationExecution.organization_id == organization_id)
        if status:
            stmt = stmt.where(AutomationExecution.status == status)

        stmt = stmt.order_by(AutomationExecution.created_at.desc())
        return paginate(db, stmt, page=page, page_size=page_size)

    @classmethod
    def list_jobs(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        status: Optional[str] = None,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[FollowUpJob], int]:
        stmt = select(FollowUpJob).where(FollowUpJob.organization_id == organization_id)
        if status:
            stmt = stmt.where(FollowUpJob.status == status)

        stmt = stmt.order_by(FollowUpJob.scheduled_at.desc())
        return paginate(db, stmt, page=page, page_size=page_size)

    @classmethod
    def get_rule(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        rule_id: uuid.UUID,
    ) -> FollowUpRule:
        rule = db.scalar(
            select(FollowUpRule).where(
                FollowUpRule.id == rule_id,
                FollowUpRule.organization_id == organization_id,
            )
        )
        if not rule:
            raise NotFoundException("Follow-up rule not found", code="RULE_NOT_FOUND")
        return rule

    @classmethod
    def delete_rule(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        rule_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> None:
        rule = cls.get_rule(db, organization_id, rule_id)
        db.delete(rule)
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="DELETE_FOLLOW_UP_RULE",
            entity_type="FOLLOW_UP_RULE",
            entity_id=rule_id,
            metadata_json={"rule_id": str(rule_id)},
        )
        db.add(audit)
        db.commit()

    @classmethod
    def set_rule_active(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        rule_id: uuid.UUID,
        is_active: bool,
        user_id: Optional[uuid.UUID] = None,
    ) -> FollowUpRule:
        rule = cls.get_rule(db, organization_id, rule_id)
        rule.is_active = is_active
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="ENABLE_FOLLOW_UP_RULE" if is_active else "DISABLE_FOLLOW_UP_RULE",
            entity_type="FOLLOW_UP_RULE",
            entity_id=rule_id,
            metadata_json={"is_active": is_active},
        )
        db.add(audit)
        db.commit()
        db.refresh(rule)
        return rule

    @classmethod
    def get_job(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
    ) -> FollowUpJob:
        job = db.scalar(
            select(FollowUpJob).where(
                FollowUpJob.id == job_id,
                FollowUpJob.organization_id == organization_id,
            )
        )
        if not job:
            raise NotFoundException("Follow-up job not found", code="JOB_NOT_FOUND")
        return job

    @classmethod
    def cancel_job(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> FollowUpJob:
        job = cls.get_job(db, organization_id, job_id)
        job.status = "cancelled"
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CANCEL_FOLLOW_UP_JOB",
            entity_type="FOLLOW_UP_JOB",
            entity_id=job_id,
            metadata_json={"status": "cancelled"},
        )
        db.add(audit)
        db.commit()
        db.refresh(job)
        return job

    @classmethod
    def retry_job(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
    ) -> FollowUpJob:
        job = cls.get_job(db, organization_id, job_id)
        job.status = "scheduled"
        job.scheduled_at = datetime.now(timezone.utc)
        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="RETRY_FOLLOW_UP_JOB",
            entity_type="FOLLOW_UP_JOB",
            entity_id=job_id,
            metadata_json={"status": "scheduled"},
        )
        db.add(audit)
        db.commit()
        db.refresh(job)
        return job

    @classmethod
    def update_job(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        job_id: uuid.UUID,
        status: Optional[str] = None,
        scheduled_at: Optional[datetime] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> FollowUpJob:
        job = cls.get_job(db, organization_id, job_id)
        if status:
            job.status = status
        if scheduled_at:
            job.scheduled_at = scheduled_at
        db.commit()
        db.refresh(job)
        return job
