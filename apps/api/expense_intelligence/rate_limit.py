import hashlib
import threading
import time
from dataclasses import dataclass

from fastapi import Request
from starlette.responses import JSONResponse


@dataclass(frozen=True)
class Limit:
    prefix: str
    methods: frozenset[str]
    requests: int
    window: int = 60


LIMITS = (
    Limit("/v1/agent/", frozenset({"POST"}), 5),
    Limit("/v1/feedback", frozenset({"POST"}), 20),
    Limit("/v1/imports", frozenset({"POST", "PUT", "DELETE"}), 20),
    Limit("/v1/receipts", frozenset({"POST", "PUT", "DELETE"}), 20),
    Limit("/v1/groups", frozenset({"POST", "PUT", "DELETE"}), 30),
    Limit("/v1/", frozenset({"GET", "POST", "PUT", "DELETE"}), 120),
)


class InstanceRateLimiter:
    """Small-demo guard; hosting edge limits remain required for multi-instance enforcement."""

    def __init__(self):
        self._counts: dict[tuple[str, str, int], int] = {}
        self._lock = threading.Lock()

    def check(self, key: str, path: str, method: str, now: float | None = None) -> tuple[bool, int, int]:
        current = int(now if now is not None else time.time())
        matching = [rule for rule in LIMITS if path.startswith(rule.prefix) and method in rule.methods]
        if not matching:
            return True, 0, 0
        rule = matching[0]
        window = current // rule.window
        bucket = (key, rule.prefix, window)
        with self._lock:
            if len(self._counts) > 10_000:
                self._counts = {item: count for item, count in self._counts.items() if item[2] >= window - 1}
            count = self._counts.get(bucket, 0) + 1
            self._counts[bucket] = count
        retry_after = rule.window - (current % rule.window)
        return count <= rule.requests, max(rule.requests - count, 0), retry_after


limiter = InstanceRateLimiter()


async def rate_limit_requests(request: Request, call_next):
    from .config import get_settings
    settings = get_settings()
    if settings.app_env == "test" or not settings.rate_limit_enabled:
        return await call_next(request)
    credential = request.headers.get("authorization") or request.headers.get("x-dev-user-id") or (request.client.host if request.client else "unknown")
    key = hashlib.sha256(credential.encode("utf-8")).hexdigest()[:24]
    allowed, remaining, retry_after = limiter.check(key, request.url.path, request.method)
    if not allowed:
        return JSONResponse({"detail": "Request limit reached; retry later"}, status_code=429, headers={"Retry-After": str(retry_after), "X-RateLimit-Remaining": "0"})
    response = await call_next(request)
    if retry_after:
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response
