import os
import uuid
from pathlib import Path
from typing import Optional

from app.core.errors import ValidationException


class StorageAdapter:
    """Secure local file storage adapter for voice samples and call recordings."""

    def __init__(self, base_path: str = "./storage"):
        self.base_path = os.path.abspath(base_path)
        os.makedirs(self.base_path, exist_ok=True)
        os.makedirs(os.path.join(self.base_path, "voice_profiles"), exist_ok=True)
        os.makedirs(os.path.join(self.base_path, "recordings"), exist_ok=True)

    def _safe_path(self, category: str, filename: str) -> str:
        # Sanitize filename and prevent path traversal
        clean_name = os.path.basename(filename)
        dest = os.path.abspath(os.path.join(self.base_path, category, clean_name))
        if not dest.startswith(self.base_path):
            raise ValidationException("Invalid storage path: path traversal detected.")
        return dest

    def save_voice_sample(self, organization_id: uuid.UUID, agent_id: uuid.UUID, filename: str, data: bytes) -> str:
        ext = os.path.splitext(filename)[1].lower() or ".wav"
        safe_filename = f"{organization_id}_{agent_id}_{uuid.uuid4().hex[:8]}{ext}"
        path = self._safe_path("voice_profiles", safe_filename)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def save_recording(self, organization_id: uuid.UUID, call_id: uuid.UUID, data: bytes, format: str = "wav") -> str:
        safe_filename = f"{organization_id}_{call_id}_{uuid.uuid4().hex[:8]}.{format}"
        path = self._safe_path("recordings", safe_filename)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def get_file(self, relative_or_abs_path: str) -> Optional[bytes]:
        full_path = os.path.abspath(relative_or_abs_path)
        if not full_path.startswith(self.base_path) or not os.path.exists(full_path):
            return None
        with open(full_path, "rb") as f:
            return f.read()

    def delete_file(self, relative_or_abs_path: str) -> bool:
        full_path = os.path.abspath(relative_or_abs_path)
        if not full_path.startswith(self.base_path) or not os.path.exists(full_path):
            return False
        try:
            os.remove(full_path)
            return True
        except OSError:
            return False
