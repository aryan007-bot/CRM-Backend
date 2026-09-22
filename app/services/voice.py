import base64
import os
from typing import Optional
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.storage.local import StorageAdapter
from app.adapters.tts.chatterbox import ChatterboxTTSAdapter
from app.core.errors import NotFoundException, ValidationException
from app.db.models.ai_agent import AiAgent, VoiceProfile
from app.db.models.audit import AuditLog

storage_adapter = StorageAdapter()
tts_adapter = ChatterboxTTSAdapter()


class VoiceService:
    @staticmethod
    def upload_voice_profile(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        agent_id: uuid.UUID,
        filename: str,
        content: bytes,
    ) -> VoiceProfile:
        # Validate agent exists in tenant
        agent = db.execute(
            select(AiAgent).where(AiAgent.organization_id == organization_id, AiAgent.id == agent_id)
        ).scalar_one_or_none()
        if not agent:
            raise NotFoundException("AI Agent not found")

        # Validate file format and size
        ext = os.path.splitext(filename)[1].lower()
        if ext not in (".wav", ".mp3", ".ogg", ".m4a"):
            raise ValidationException("Only audio files (.wav, .mp3, .ogg, .m4a) are allowed.")
        if len(content) > 15 * 1024 * 1024:
            raise ValidationException("Audio file exceeds 15MB limit.")
        if len(content) < 100:
            raise ValidationException("Audio file is empty or corrupted.")

        # Save securely
        audio_path = storage_adapter.save_voice_sample(organization_id, agent_id, filename, content)

        # Check for existing profile
        existing_profile = db.execute(
            select(VoiceProfile).where(VoiceProfile.agent_id == agent_id)
        ).scalar_one_or_none()

        if existing_profile:
            storage_adapter.delete_file(existing_profile.audio_path)
            existing_profile.name = filename
            existing_profile.audio_path = audio_path
            existing_profile.status = "READY"
            profile = existing_profile
        else:
            profile = VoiceProfile(
                organization_id=organization_id,
                agent_id=agent_id,
                name=filename,
                provider="chatterbox",
                audio_path=audio_path,
                sample_rate=24000,
                duration_seconds=5.0,
                status="READY",
            )
            db.add(profile)

        # Recompute agent readiness
        agent.voice_profile = profile
        if agent.name and len(agent.system_prompt) >= 10 and len(agent.disclosure) >= 10:
            agent.status = "READY"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="UPLOAD_VOICE",
            entity_type="voice_profile",
            entity_id=profile.id,
            metadata_json={"agent_id": str(agent_id), "filename": filename},
        )
        db.add(audit)
        db.commit()
        db.refresh(profile)
        return profile

    @staticmethod
    def delete_voice_profile(
        db: Session,
        organization_id: uuid.UUID,
        user_id: Optional[uuid.UUID],
        agent_id: uuid.UUID,
    ):
        agent = db.execute(
            select(AiAgent).where(AiAgent.organization_id == organization_id, AiAgent.id == agent_id)
        ).scalar_one_or_none()
        if not agent:
            raise NotFoundException("AI Agent not found")

        profile = db.execute(
            select(VoiceProfile).where(VoiceProfile.agent_id == agent_id)
        ).scalar_one_or_none()
        if not profile:
            raise NotFoundException("Voice profile not found")

        storage_adapter.delete_file(profile.audio_path)
        db.delete(profile)
        agent.status = "DRAFT"

        audit = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action="DELETE_VOICE",
            entity_type="voice_profile",
            entity_id=profile.id,
            metadata_json={"agent_id": str(agent_id)},
        )
        db.add(audit)
        db.commit()

    @staticmethod
    async def generate_preview(
        db: Session,
        organization_id: uuid.UUID,
        agent_id: uuid.UUID,
        text: str,
    ) -> dict:
        agent = db.execute(
            select(AiAgent).where(AiAgent.organization_id == organization_id, AiAgent.id == agent_id)
        ).scalar_one_or_none()
        if not agent:
            raise NotFoundException("AI Agent not found")

        profile = db.execute(
            select(VoiceProfile).where(VoiceProfile.agent_id == agent_id)
        ).scalar_one_or_none()

        audio_path = profile.audio_path if profile else None
        res = await tts_adapter.synthesize(text=text, voice_profile_path=audio_path, language=agent.language)

        return {
            "audio_base64": base64.b64encode(res.audio_data).decode("ascii"),
            "sample_rate": res.sample_rate,
            "duration_seconds": res.duration_seconds,
            "format": res.format,
        }
