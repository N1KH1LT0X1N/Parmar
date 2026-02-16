import asyncio
import secrets
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request

from app.config import Settings, get_settings


class InMemoryRateLimiter:
    def __init__(self):
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.monotonic()
        cutoff = now - window_seconds
        async with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


def client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def enforce_rate_limit(
    request: Request,
    limiter: InMemoryRateLimiter,
    bucket: str,
    max_per_minute: int,
) -> None:
    key = f"{bucket}:{client_identifier(request)}"
    allowed = await limiter.allow(key=key, limit=max_per_minute, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def require_dashboard_auth(
    request: Request,
    current_settings: Settings = Depends(get_settings),
) -> None:
    # Keep local/dev ergonomics: if unset, auth is disabled.
    if not current_settings.dashboard_api_key:
        return

    provided = request.headers.get(current_settings.dashboard_api_key_header, "")
    if not provided or not secrets.compare_digest(provided, current_settings.dashboard_api_key):
        raise HTTPException(status_code=401, detail="Invalid dashboard API key")
