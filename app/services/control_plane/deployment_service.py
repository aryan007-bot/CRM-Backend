from datetime import datetime, timezone
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.deployment.provider import get_deployment_provider
from app.core.errors import NotFoundException
from app.db.models.audit import AuditLog
from app.db.models.deployment import DeploymentRecord, EnvironmentRecord
from app.services.control_plane.event_bus import event_bus


class DeploymentService:
    """Manages deployment workflows, environments, and rollbacks via DeploymentProvider."""

    @staticmethod
    def ensure_default_environments(db: Session):
        envs = [
            ("production", "PRODUCTION", "1.0.0"),
            ("staging", "STAGING", "1.0.0"),
            ("development", "DEVELOPMENT", "1.0.0"),
        ]
        for name, env_type, ver in envs:
            existing = db.scalar(select(EnvironmentRecord).where(EnvironmentRecord.name == name))
            if not existing:
                rec = EnvironmentRecord(
                    name=name,
                    environment_type=env_type,
                    status="HEALTHY",
                    version=ver,
                )
                db.add(rec)
        db.commit()

    @staticmethod
    def trigger_deployment(
        db: Session,
        environment_id: uuid.UUID,
        version: str,
        commit_sha: str,
        deployed_by: Optional[uuid.UUID] = None,
    ) -> DeploymentRecord:
        env = db.scalar(select(EnvironmentRecord).where(EnvironmentRecord.id == environment_id))
        if not env:
            raise NotFoundException(f"Environment {environment_id} not found", code="ENVIRONMENT_NOT_FOUND")

        now = datetime.now(timezone.utc)
        record = DeploymentRecord(
            scope="PLATFORM",
            environment_id=environment_id,
            version=version,
            commit_sha=commit_sha,
            status="RUNNING",
            started_at=now,
            deployed_by=deployed_by,
            migration_status="UP_TO_DATE",
            health_status="HEALTHY",
        )
        db.add(record)
        db.flush()

        provider = get_deployment_provider()
        res = provider.deploy(env.name, version, commit_sha)

        record.status = res.get("status", "SUCCESS")
        record.completed_at = datetime.now(timezone.utc)
        env.version = version

        audit = AuditLog(
            organization_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=deployed_by,
            action="DEPLOYMENT_REQUESTED",
            entity_type="deployment",
            entity_id=record.id,
            metadata_json={"version": version, "commit_sha": commit_sha, "environment": env.name},
        )
        db.add(audit)

        event_bus.emit_operational_event(
            db=db,
            event_type="deployment.completed",
            scope="PLATFORM",
            entity_type="deployment",
            entity_id=str(record.id),
            severity="INFO",
            message=f"Deployed {version} to {env.name}",
            payload={"version": version, "status": record.status},
        )
        db.commit()
        return record

    @staticmethod
    def rollback_deployment(
        db: Session,
        deployment_id: uuid.UUID,
        target_version: Optional[str] = None,
        user_id: Optional[uuid.UUID] = None,
    ) -> DeploymentRecord:
        record = db.scalar(select(DeploymentRecord).where(DeploymentRecord.id == deployment_id))
        if not record:
            raise NotFoundException(f"Deployment {deployment_id} not found", code="DEPLOYMENT_NOT_FOUND")

        env = db.scalar(select(EnvironmentRecord).where(EnvironmentRecord.id == record.environment_id))
        target_ver = target_version or "1.0.0"

        provider = get_deployment_provider()
        res = provider.rollback(env.name if env else "production", target_ver)

        record.status = res.get("status", "ROLLED_BACK")
        if env:
            env.version = target_ver

        audit = AuditLog(
            organization_id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
            user_id=user_id,
            action="DEPLOYMENT_ROLLBACK_REQUESTED",
            entity_type="deployment",
            entity_id=record.id,
            metadata_json={"target_version": target_ver},
        )
        db.add(audit)

        event_bus.emit_operational_event(
            db=db,
            event_type="deployment.rollback",
            scope="PLATFORM",
            entity_type="deployment",
            entity_id=str(record.id),
            severity="WARNING",
            message=f"Rollback to {target_ver} executed",
        )
        db.commit()
        return record

