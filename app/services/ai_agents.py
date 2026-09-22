from typing import List, Optional, Tuple
import uuid

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import NotFoundException, ValidationException
from app.db.models.ai_agent import AiAgent, VoiceProfile
from app.db.models.audit import AuditLog
from app.schemas.ai_agent import AiAgentCreate, AiAgentUpdate
from app.utils.pagination import paginate


class AiAgentService:
    @staticmethod
    def _compute_status(agent: AiAgent) -> str:
        """Calculates whether an agent has all required configuration to be READY."""
        if not agent.is_active:
            return "INACTIVE"
        if (
            agent.name
            and agent.system_prompt
            and len(agent.system_prompt.strip()) >= 10
            and agent.disclosure
            and len(agent.disclosure.strip()) >= 10
            and agent.voice_profile is not None
            and agent.voice_profile.status == "READY"
        ):
            return "READY"
        return "DRAFT"

    @classmethod
    def create_agent(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        payload: AiAgentCreate,
    ) -> AiAgent:
        agent = AiAgent(
            organization_id=organization_id,
            name=payload.name.strip(),
            language=payload.language,
            model=payload.model,
            system_prompt=payload.system_prompt.strip(),
            disclosure=payload.disclosure.strip(),
            status="DRAFT",
            is_active=True,
        )
        agent.status = cls._compute_status(agent)
        db.add(agent)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="CREATE",
            entity_type="ai_agent",
            entity_id=agent.id,
            metadata_json={"name": agent.name, "model": agent.model},
        )
        db.add(audit)
        db.commit()
        db.refresh(agent)
        return agent

    @staticmethod
    def get_agent(db: Session, organization_id: uuid.UUID, agent_id: uuid.UUID) -> AiAgent:
        query = (
            select(AiAgent)
            .where(AiAgent.organization_id == organization_id, AiAgent.id == agent_id)
            .options(joinedload(AiAgent.voice_profile))
        )
        agent = db.execute(query).unique().scalar_one_or_none()
        if not agent:
            raise NotFoundException("AI Agent not found")
        return agent

    @classmethod
    def update_agent(
        cls,
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        agent_id: uuid.UUID,
        payload: AiAgentUpdate,
    ) -> AiAgent:
        agent = cls.get_agent(db, organization_id, agent_id)

        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            if key == "name" and value is not None:
                agent.name = value.strip()
            elif key == "system_prompt" and value is not None:
                agent.system_prompt = value.strip()
            elif key == "disclosure" and value is not None:
                agent.disclosure = value.strip()
            elif key in ("language", "model", "is_active"):
                setattr(agent, key, value)

        agent.status = cls._compute_status(agent)
        db.flush()

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="UPDATE",
            entity_type="ai_agent",
            entity_id=agent.id,
            metadata_json={"status": agent.status},
        )
        db.add(audit)
        db.commit()
        db.refresh(agent)
        return agent

    @staticmethod
    def list_agents(
        db: Session,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[AiAgent], int]:
        query = (
            select(AiAgent)
            .where(AiAgent.organization_id == organization_id)
            .options(joinedload(AiAgent.voice_profile))
            .order_by(desc(AiAgent.created_at))
        )
        return paginate(db, query, page, page_size)
