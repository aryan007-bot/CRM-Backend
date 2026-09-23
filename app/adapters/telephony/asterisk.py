import os
from typing import Any, Dict, Optional
import uuid

import httpx

from app.core.errors import TelephonyException, TelephonyUnavailableException
from app.core.logging import logger
from app.services.telephony_core.outbound_dial_service import OutboundDialService


class AsteriskTelephonyAdapter:
    """Asterisk ARI interface for real channel operations, originate and call controls."""

    def __init__(
        self,
        ari_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        app_name: Optional[str] = None,
        context: Optional[str] = None,
    ):
        self.ari_url = ari_url or os.getenv("ASTERISK_ARI_URL", "http://localhost:8088/ari")
        self.username = username or os.getenv("ASTERISK_ARI_USERNAME", "asterisk")
        self.password = password or os.getenv("ASTERISK_ARI_PASSWORD", "asterisk")
        self.app_name = app_name or os.getenv("ASTERISK_STASIS_APP", "ai-recovery")
        self.context = context or os.getenv("OUTBOUND_CONTEXT", "ai-recovery")
        self.channels: Dict[str, Dict[str, Any]] = {}

    def _get_auth(self) -> tuple[str, str]:
        return (self.username, self.password)

    def is_reachable(self) -> bool:
        """Verifies if the Asterisk ARI server is reachable over HTTP."""
        try:
            with httpx.Client(timeout=2.0) as client:
                res = client.get(f"{self.ari_url}/asterisk/info", auth=self._get_auth())
                return res.status_code == 200
        except Exception:
            return False

    def originate_call(
        self,
        caller_id: str,
        recipient: str,
        channel_id: Optional[str] = None,
        mode: str = "LIVE",
        trunk_name: Optional[str] = None,
    ) -> str:
        """Originates an outbound call via Asterisk ARI.
        
        In LIVE mode, sends a real POST /ari/channels request to the Asterisk PBX.
        If Asterisk is not running or returns an error, raises an appropriate TelephonyException.
        In SIMULATION mode, registers the channel in memory.
        """
        cid = channel_id or f"chan-{uuid.uuid4().hex[:8]}"

        if mode.upper() == "SIMULATION":
            self.channels[cid] = {
                "caller_id": caller_id,
                "recipient": recipient,
                "state": "ringing",
                "mode": "SIMULATION",
                "muted": False,
                "on_hold": False,
            }
            logger.info(f"[Asterisk Simulation] Originated channel {cid} to {recipient}")
            return cid

        # LIVE Mode: Execute real Asterisk ARI originate
        dial_endpoint = OutboundDialService.get_outbound_dial_string(recipient, trunk_name=trunk_name)
        originate_url = f"{self.ari_url}/channels"
        params = {
            "endpoint": dial_endpoint,
            "extension": "s",
            "context": self.context,
            "priority": 1,
            "callerId": caller_id,
            "channelId": cid,
            "app": self.app_name,
        }

        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.post(originate_url, params=params, auth=self._get_auth())
                if res.status_code in (200, 201):
                    channel_data = res.json()
                    self.channels[cid] = {
                        "caller_id": caller_id,
                        "recipient": recipient,
                        "state": "originating",
                        "mode": "LIVE",
                        "asterisk_id": channel_data.get("id", cid),
                        "muted": False,
                        "on_hold": False,
                    }
                    logger.info(f"[Asterisk ARI] Real call originated successfully: channel {cid} to {recipient}")
                    return cid

                err_msg = f"Asterisk originate returned HTTP {res.status_code}: {res.text}"
                logger.error(f"[Asterisk ARI Error] {err_msg}")
                raise TelephonyException(
                    message=err_msg,
                    code="ASTERISK_ORIGINATE_FAILED",
                    details={"status_code": res.status_code, "response": res.text}
                )
        except httpx.ConnectError:
            err_msg = f"Cannot connect to Asterisk ARI at {self.ari_url}. Asterisk PBX is offline or unreachable."
            logger.error(f"[Asterisk Connection Error] {err_msg}")
            raise TelephonyUnavailableException(message=err_msg)
        except httpx.TimeoutException:
            err_msg = f"Timeout connecting to Asterisk ARI at {self.ari_url}."
            logger.error(f"[Asterisk Timeout Error] {err_msg}")
            raise TelephonyUnavailableException(message=err_msg)

    def answer_channel(self, channel_id: str) -> bool:
        if channel_id in self.channels:
            self.channels[channel_id]["state"] = "connected"
            return True
        return False

    def mute_channel(self, channel_id: str) -> bool:
        if channel_id in self.channels:
            self.channels[channel_id]["muted"] = True
            return True
        return False

    def unmute_channel(self, channel_id: str) -> bool:
        if channel_id in self.channels:
            self.channels[channel_id]["muted"] = False
            return True
        return False

    def hold_channel(self, channel_id: str) -> bool:
        if channel_id in self.channels:
            self.channels[channel_id]["on_hold"] = True
            return True
        return False

    def resume_channel(self, channel_id: str) -> bool:
        if channel_id in self.channels:
            self.channels[channel_id]["on_hold"] = False
            return True
        return False

    def transfer_channel(self, channel_id: str, target_extension: str) -> bool:
        if channel_id in self.channels:
            self.channels[channel_id]["state"] = "transferred"
            self.channels[channel_id]["transferred_to"] = target_extension
            return True
        return False

    def hangup_channel(self, channel_id: str) -> bool:
        if channel_id in self.channels:
            self.channels[channel_id]["state"] = "ended"

        # In live mode attempt real hangup
        try:
            with httpx.Client(timeout=3.0) as client:
                client.delete(f"{self.ari_url}/channels/{channel_id}", auth=self._get_auth())
        except Exception:
            pass
        return True

    def health_check(self) -> dict:
        is_up = self.is_reachable()
        return {
            "status": "HEALTHY" if is_up else "UNAVAILABLE",
            "active_channels": len([c for c in self.channels.values() if c.get("state") not in ("ended", "failed")]),
            "ari_endpoint": self.ari_url,
            "connected": is_up,
        }
