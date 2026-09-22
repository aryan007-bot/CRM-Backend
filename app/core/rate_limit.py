"""Minimal in-process fixed-window rate limiter.

Phase 1 intentionally avoids adding a Redis/Valkey-backed limiter subsystem.
This protects the few abuse-prone endpoints (login, upload, validate, confirm)
within a single worker process. Behind multiple workers the effective limit is
``limit * workers``; move to a shared store when Phase 2 puts Valkey on the
request path.
"""

import time
from threading import Lock
from typing import Callable, Dict, Tuple

from fastapi import Request

from app.core.config import settings
from app.core.errors import AppException

WINDOW_SECONDS = 60


class RateLimitExceededException(AppException):
    def __init__(self, retry_after_seconds: int):
        super().__init__(
            code="RATE_LIMITED",
            message="Too many requests. Please wait a moment and try again.",
            status_code=429,
            details={"retry_after_seconds": retry_after_seconds},
        )


class FixedWindowRateLimiter:
    """Thread-safe fixed-window counter keyed by (bucket, client identity)."""

    def __init__(self) -> None:
        self._hits: Dict[Tuple[str, str], Tuple[int, float]] = {}
        self._lock = Lock()

    @staticmethod
    def _client_key(request: Request) -> str:
        # Trust the proxy-provided client IP when present (Cloudflare / Nginx),
        # otherwise fall back to the socket peer address.
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def check(self, bucket: str, request: Request, limit_per_minute: int) -> None:
        now = time.monotonic()
        key = (bucket, self._client_key(request))

        with self._lock:
            count, window_start = self._hits.get(key, (0, now))

            if now - window_start >= WINDOW_SECONDS:
                count, window_start = 0, now

            if count >= limit_per_minute:
                retry_after = max(1, int(WINDOW_SECONDS - (now - window_start)))
                raise RateLimitExceededException(retry_after)

            self._hits[key] = (count + 1, window_start)

            # Opportunistic cleanup keeps the dict from growing without bound.
            if len(self._hits) > 10_000:
                self._hits = {
                    k: v for k, v in self._hits.items() if now - v[1] < WINDOW_SECONDS
                }

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = FixedWindowRateLimiter()


def rate_limit(bucket: str, limit: int) -> Callable[[Request], None]:
    """FastAPI dependency enforcing a per-client request limit."""

    def dependency(request: Request) -> None:
        if not settings.RATE_LIMIT_ENABLED or settings.ENVIRONMENT == "test":
            return
        limiter.check(bucket, request, limit)

    return dependency
