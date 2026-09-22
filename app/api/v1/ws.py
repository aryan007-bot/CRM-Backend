from typing import Optional
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
import jwt
from sqlalchemy import select

from app.core.config import settings
from app.db.models.user import User
from app.db.session import SessionLocal
from app.services.realtime.manager import realtime_manager

router = APIRouter(tags=["Realtime WebSocket"])


def _authenticate_ws(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        user_id = uuid.UUID(user_id_str)
        with SessionLocal() as db:
            user = db.execute(select(User).where(User.id == user_id, User.is_active == True)).scalar_one_or_none()
            return user
    except Exception:
        return None


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
):
    user = _authenticate_ws(token)
    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    org_id = user.organization_id
    await realtime_manager.connect(websocket, org_id)

    try:
        while True:
            # Keep connection open and accept client heartbeats/pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        realtime_manager.disconnect(websocket, org_id)
    except Exception:
        realtime_manager.disconnect(websocket, org_id)
