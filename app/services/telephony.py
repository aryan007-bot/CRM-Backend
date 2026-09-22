from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.adapters.gsm.gateway import GSMGatewayAdapter
from app.adapters.llm.gateway import AIGatewayAdapter
from app.adapters.stt.conformer import IndicConformerSTTAdapter
from app.adapters.telephony.asterisk import AsteriskTelephonyAdapter
from app.adapters.tts.chatterbox import ChatterboxTTSAdapter
from app.core.errors import NotFoundException
from app.db.models.telephony import AiServiceStatus, TelephonyGateway
from app.schemas.telephony import GatewayHeartbeat, TelephonyGatewayCreate
from app.utils.pagination import paginate

gsm_adapter = GSMGatewayAdapter()
asterisk_adapter = AsteriskTelephonyAdapter()
stt_adapter = IndicConformerSTTAdapter()
tts_adapter = ChatterboxTTSAdapter()
llm_adapter = AIGatewayAdapter()


class TelephonyService:
    @staticmethod
    def create_gateway(
        db: Session,
        organization_id: uuid.UUID,
        payload: TelephonyGatewayCreate,
    ) -> TelephonyGateway:
        gw = TelephonyGateway(
            organization_id=organization_id,
            name=payload.name.strip(),
            gateway_type=payload.gateway_type.upper(),
            host=payload.host.strip(),
            port=payload.port,
            status="ONLINE",
            signal_strength=85,
            active_channels=0,
            last_seen_at=datetime.now(timezone.utc),
        )
        db.add(gw)
        db.commit()
        db.refresh(gw)
        return gw

    @staticmethod
    def list_gateways(
        db: Session,
        organization_id: uuid.UUID,
        page: int = 1,
        page_size: int = 25,
    ) -> Tuple[List[TelephonyGateway], int]:
        query = (
            select(TelephonyGateway)
            .where(TelephonyGateway.organization_id == organization_id)
            .order_by(desc(TelephonyGateway.created_at))
        )
        return paginate(db, query, page, page_size)

    @staticmethod
    def get_gateway(
        db: Session,
        organization_id: uuid.UUID,
        gateway_id: uuid.UUID,
    ) -> TelephonyGateway:
        gw = db.execute(
            select(TelephonyGateway).where(
                TelephonyGateway.organization_id == organization_id,
                TelephonyGateway.id == gateway_id,
            )
        ).scalar_one_or_none()
        if not gw:
            raise NotFoundException("Telephony gateway not found")
        return gw

    @staticmethod
    def record_heartbeat(
        db: Session,
        organization_id: uuid.UUID,
        gateway_id: uuid.UUID,
        payload: GatewayHeartbeat,
    ) -> TelephonyGateway:
        gw = TelephonyService.get_gateway(db, organization_id, gateway_id)
        gw.last_seen_at = datetime.now(timezone.utc)
        gw.status = "ONLINE"
        if payload.signal_strength is not None:
            gw.signal_strength = payload.signal_strength
        if payload.network_operator is not None:
            gw.network_operator = payload.network_operator
        gw.active_channels = payload.active_channels
        db.commit()
        db.refresh(gw)
        return gw

    @staticmethod
    def get_telephony_status(db: Session, organization_id: uuid.UUID) -> dict:
        ast_health = asterisk_adapter.health_check()
        gateways = db.execute(
            select(TelephonyGateway).where(TelephonyGateway.organization_id == organization_id)
        ).scalars().all()

        online_count = sum(1 for g in gateways if g.status == "ONLINE")
        return {
            "asterisk_status": ast_health["status"],
            "active_channels": ast_health["active_channels"],
            "gateways_online": online_count,
            "gateways_total": len(gateways),
        }

    @staticmethod
    def get_ai_status() -> dict:
        stt_info = stt_adapter.health_check()
        tts_info = tts_adapter.health_check()
        llm_info = llm_adapter.health_check()
        vad_info = {
            "service_type": "VAD",
            "provider": "silero",
            "model": "silero-vad-v5",
            "status": "HEALTHY",
            "latency_ms": 5,
        }

        services = [
            {
                "service_type": s["service_type"],
                "provider": s["provider"],
                "model": s.get("model"),
                "status": s["status"],
                "latency_ms": s.get("latency_ms"),
                "last_checked_at": datetime.now(timezone.utc),
            }
            for s in [stt_info, llm_info, tts_info, vad_info]
        ]
        return {
            "services": services,
            "overall_status": "HEALTHY",
        }
