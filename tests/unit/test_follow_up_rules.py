import uuid
from sqlalchemy.orm import Session

from app.db.models.automation import FollowUpJob, FollowUpRule
from app.db.models.organization import Organization
from app.schemas.automation import FollowUpRuleCreate
from app.services.recovery.automation import FollowUpEngine


def test_follow_up_rule_evaluation_and_job_generation(db: Session, test_org_a: Organization):
    # Create rule: on ptp_created -> send_sms
    rule_data = FollowUpRuleCreate(
        name="PTP SMS Reminder",
        event_trigger="ptp_created",
        action_type="send_sms",
        action_template="Thank you for committing to pay on {date}. Link: {link}",
        is_active=True,
        delay_minutes=0,
    )
    rule = FollowUpEngine.create_rule(db, test_org_a.id, rule_data)
    assert rule.id is not None

    # Dispatch trigger
    ptp_id = uuid.uuid4()
    executions = FollowUpEngine.dispatch_trigger(
        db=db,
        organization_id=test_org_a.id,
        trigger_event="ptp_created",
        target_entity_type="ptp",
        target_entity_id=ptp_id,
        recipient="+919876543210",
    )
    assert len(executions) == 1
    assert executions[0].status == "executed"

    jobs = FollowUpEngine.list_jobs(db, test_org_a.id)[0]
    assert len(jobs) == 1
    assert jobs[0].recipient == "+919876543210"
    assert jobs[0].status == "sent"

    # Test idempotency: second dispatch for same target entity & trigger should not create duplicate
    dup_executions = FollowUpEngine.dispatch_trigger(
        db=db,
        organization_id=test_org_a.id,
        trigger_event="ptp_created",
        target_entity_type="ptp",
        target_entity_id=ptp_id,
        recipient="+919876543210",
    )
    assert len(dup_executions) == 0
