import uuid
from typing import Any, Dict, Optional


class AsteriskTelephonyAdapter:
    """Asterisk ARI/AMI interface for channel operations and call controls."""

    def __init__(self, ari_url: str = "http://localhost:8088/ari", username: str = "asterisk", password: str = "asterisk"):
        self.ari_url = ari_url
        self.username = username
        self.password = password
        self.status = "ONLINE"
        self.channels: Dict[str, Dict[str, Any]] = {}

    def originate_call(self, caller_id: str, recipient: str, channel_id: Optional[str] = None) -> str:
        cid = channel_id or f"chan-{uuid.uuid4().hex[:8]}"
        self.channels[cid] = {
            "caller_id": caller_id,
            "recipient": recipient,
            "state": "ringing",
            "muted": False,
            "on_hold": False,
        }
        return cid

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
            return True
        return False

    def health_check(self) -> dict:
        return {
            "status": self.status,
            "active_channels": len([c for c in self.channels.values() if c["state"] != "ended"]),
            "ari_endpoint": self.ari_url,
        }
