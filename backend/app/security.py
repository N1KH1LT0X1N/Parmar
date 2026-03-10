import asyncio
import base64
import binascii
import hashlib
import hmac
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
            if not bucket:
                self._hits.pop(key, None)
                bucket = self._hits[key]
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True


def client_identifier(request: Request, *, trust_proxy_headers: bool = False) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if trust_proxy_headers and forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def enforce_rate_limit(
    request: Request,
    limiter: InMemoryRateLimiter,
    bucket: str,
    max_per_minute: int,
    trust_proxy_headers: bool = False,
) -> None:
    key = f"{bucket}:{client_identifier(request, trust_proxy_headers=trust_proxy_headers)}"
    allowed = await limiter.allow(key=key, limit=max_per_minute, window_seconds=60)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def _session_secret(current_settings: Settings) -> str:
    return current_settings.dashboard_session_signing_secret()


def build_dashboard_session_token(current_settings: Settings) -> str:
    secret = _session_secret(current_settings)
    if not secret:
        return ""

    expires_at = int(time.time()) + current_settings.dashboard_session_ttl_seconds
    payload = f"dashboard:{expires_at}"
    signature = hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    raw = f"{expires_at}:{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def has_valid_dashboard_session(request: Request, current_settings: Settings) -> bool:
    if not current_settings.dashboard_auth_enabled():
        return True

    token = request.cookies.get(current_settings.dashboard_session_cookie_name, "")
    if not token:
        return False

    try:
        decoded = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
        expires_text, signature = decoded.split(":", 1)
        expires_at = int(expires_text)
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return False

    if expires_at <= int(time.time()):
        return False

    payload = f"dashboard:{expires_at}"
    expected = hmac.new(
        _session_secret(current_settings).encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return secrets.compare_digest(signature, expected)


def require_dashboard_auth(
    request: Request,
    current_settings: Settings = Depends(get_settings),
) -> None:
    # Keep local/dev ergonomics: if unset, auth is disabled.
    if not current_settings.dashboard_auth_enabled():
        return

    if has_valid_dashboard_session(request, current_settings):
        return

    provided = request.headers.get(current_settings.dashboard_api_key_header, "")
    if not provided or not secrets.compare_digest(provided, current_settings.dashboard_api_key):
        raise HTTPException(status_code=401, detail="Invalid dashboard API key")
