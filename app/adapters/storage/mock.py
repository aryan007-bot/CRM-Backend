from typing import Dict

from app.adapters.base import StorageProvider


class MockStorageProvider(StorageProvider):
    def __init__(self):
        self.files: Dict[str, bytes] = {}

    async def save_file(self, path_or_key: str, content: bytes) -> str:
        clean = path_or_key.lstrip("/\\")
        self.files[clean] = content
        return f"mock://storage/{clean}"

    async def get_file(self, path_or_key: str) -> bytes:
        clean = path_or_key.lstrip("/\\")
        if clean not in self.files:
            raise FileNotFoundError(f"File {path_or_key} not found in mock storage.")
        return self.files[clean]

    async def file_exists(self, path_or_key: str) -> bool:
        clean = path_or_key.lstrip("/\\")
        return clean in self.files

    async def delete_file(self, path_or_key: str) -> bool:
        clean = path_or_key.lstrip("/\\")
        if clean in self.files:
            del self.files[clean]
            return True
        return False
