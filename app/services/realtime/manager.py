import asyncio
from datetime import datetime, timezone
import json
from typing import Any, Dict, List, Optional, Set
import uuid

from fastapi import WebSocket


class RealtimeManager:
    """Manages active WebSockets, tenant-scoped rooms, and ordered event delivery."""

    def __init__(self):
        # Maps organization_id -> Set of active WebSocket connections
        self._org_connections: Dict[uuid.UUID, Set[WebSocket]] = {}
        # Maps call_id -> current integer sequence number
        self._call_sequences: Dict[uuid.UUID, int] = {}
        # Lock for thread-safe/async-safe sequence generation
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, organization_id: uuid.UUID):
        await websocket.accept()
        if organization_id not in self._org_connections:
            self._org_connections[organization_id] = set()
        self._org_connections[organization_id].add(websocket)

    def disconnect(self, websocket: WebSocket, organization_id: uuid.UUID):
        if organization_id in self._org_connections:
            self._org_connections[organization_id].discard(websocket)
            if not self._org_connections[organization_id]:
                del self._org_connections[organization_id]

    async def get_next_sequence(self, key_id: uuid.UUID) -> int:
        async with self._lock:
            seq = self._call_sequences.get(key_id, 0) + 1
            self._call_sequences[key_id] = seq
            return seq

    async def broadcast_event(
        self,
        organization_id: uuid.UUID,
        call_id: Optional[uuid.UUID] = None,
        event_type: str = "",
        data: Optional[Dict[str, Any]] = None,
        sequence: Optional[int] = None,
    ) -> dict:
        """Broadcasts a typed, ordered event to all active clients in the organization."""
        payload_data = data or {}
        if sequence is None:
            seq_key = call_id if call_id is not None else organization_id
            sequence = await self.get_next_sequence(seq_key)

        envelope = {
            "call_id": str(call_id) if call_id is not None else "",
            "sequence": sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event_type,
            "data": payload_data,
        }

        connections = self._org_connections.get(organization_id, set()).copy()
        for ws in connections:
            try:
                await ws.send_json(envelope)
            except Exception:
                self.disconnect(ws, organization_id)

        return envelope


# Global singleton realtime manager instance
realtime_manager = RealtimeManager()
