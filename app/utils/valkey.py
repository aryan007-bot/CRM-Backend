from typing import Tuple

from app.core.config import settings
from app.core.logging import logger


def check_valkey_health() -> Tuple[bool, str]:
    """Checks Valkey / Redis availability if configured.
    Returns (is_healthy, message).
    """
    if not settings.VALKEY_URL:
        return True, "Valkey not configured"

    try:
        import socket
        import urllib.parse

        # Lightweight TCP socket check without pulling heavyweight client
        parsed = urllib.parse.urlparse(settings.VALKEY_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0)
        result = sock.connect_ex((host, port))
        sock.close()

        if result == 0:
            return True, "Valkey reachable"
        else:
            return False, f"Valkey connection failed (port {port} not reachable)"
    except Exception as e:
        logger.warning(f"Valkey health check error: {str(e)}")
        return False, str(e)
