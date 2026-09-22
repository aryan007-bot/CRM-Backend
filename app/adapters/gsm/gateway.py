from datetime import datetime, timezone
from typing import Dict, Optional


class GSMGatewayAdapter:
    """Adapter for gsm2sip / Android SIM Gateway integration with heartbeat tracking."""

    def __init__(self, heartbeat_timeout_seconds: int = 60):
        self.heartbeat_timeout = heartbeat_timeout_seconds
        self._gateways: Dict[str, dict] = {}

    def record_heartbeat(
        self,
        gateway_id: str,
        signal_strength: int = 85,
        network_operator: str = "Airtel",
        active_calls: int = 0,
    ) -> dict:
        now = datetime.now(timezone.utc)
        gw_info = {
            "gateway_id": gateway_id,
            "status": "ONLINE",
            "signal_strength": max(0, min(100, signal_strength)),
            "network_operator": network_operator,
            "active_calls": active_calls,
            "last_seen": now,
        }
        self._gateways[gateway_id] = gw_info
        return gw_info

    def get_status(self, gateway_id: str) -> str:
        if gateway_id not in self._gateways:
            return "OFFLINE"
        info = self._gateways[gateway_id]
        now = datetime.now(timezone.utc)
        elapsed = (now - info["last_seen"]).total_seconds()
        if elapsed > self.heartbeat_timeout:
            info["status"] = "OFFLINE"
            return "OFFLINE"
        return info["status"]
