import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from sqlalchemy.orm import Session

from app.db.models.security_event import OperationalEvent, SecurityEvent
from app.services.realtime.manager import realtime_manager


def _sanitize_payload(obj: Any) -> Any:
    if isinstance(obj, dict):
        res = {}
        for k, v in obj.items():
            if any(s in str(k).lower() for s in ("password", "api_key", "secret", "token", "credential")):
                res[str(k)] = "******"
            else:
                res[str(k)] = _sanitize_payload(v)
        return res
    elif isinstance(obj, (list, tuple, set)):
        return [_sanitize_payload(i) for i in obj]
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    return obj


class EventBus:
    """Dispatches operational and security events to database log and WebSocket streams."""

    @staticmethod
    def emit_operational_event(
        db: Session,
        event_type: str,
        scope: str = "PLATFORM",
        organization_id: Optional[uuid.UUID] = None,
        entity_type: str = "SYSTEM",
        entity_id: Optional[str] = None,
        severity: str = "INFO",
        message: str = "",
        payload: Optional[Dict[str, Any]] = None,
    ) -> OperationalEvent:
        safe_payload = _sanitize_payload(payload or {})

        event = OperationalEvent(
            event_type=event_type,
            scope=scope,
            organization_id=organization_id,
            entity_type=entity_type,
            entity_id=entity_id,
            severity=severity,
            message=message,
            payload_safe=safe_payload,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(event)
        db.flush()


        # Realtime WebSocket notification
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(
                    realtime_manager.broadcast_event(
                        organization_id=organization_id,
                        event_type=event_type,
                        data={
                            "event_id": str(event.id),
                            "entity_type": entity_type,
                            "entity_id": entity_id,
                            "severity": severity,
                            "message": message,
                            "payload": safe_payload,
                        },
                    )
                )
        except Exception:
            pass


        return event

    @staticmethod
    def emit_security_event(
        db: Session,
        event_type: str,
        resource_type: str,
        severity: str = "MEDIUM",
        scope: str = "PLATFORM",
        organization_id: Optional[uuid.UUID] = None,
        actor_id: Optional[uuid.UUID] = None,
        ip_address: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> SecurityEvent:
        safe_details = _sanitize_payload(details or {})

        event = SecurityEvent(
            scope=scope,
            organization_id=organization_id,
            event_type=event_type,
            severity=severity,
            actor_id=actor_id,
            ip_address=ip_address,
            resource_type=resource_type,
            resource_id=resource_id,
            safe_details=safe_details,
            timestamp=datetime.now(timezone.utc),
        )
        db.add(event)
        db.flush()
        return event


event_bus = EventBus()
