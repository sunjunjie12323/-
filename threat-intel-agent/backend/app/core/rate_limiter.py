import time
from typing import Dict, Optional, Tuple

from fastapi import Request, Response
from loguru import logger

from app.config import settings
from app.core.exceptions import RateLimitExceededException


class TokenBucket:
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()

    def consume(self, tokens: int = 1) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def retry_after(self) -> float:
        deficit = 1.0 - self.tokens
        if deficit <= 0:
            return 0.0
        return deficit / self.refill_rate


class RateLimiter:
    def __init__(
        self,
        requests_per_minute: int = 0,
    ):
        self.requests_per_minute = requests_per_minute or settings.RATE_LIMIT_PER_MINUTE
        self.capacity = self.requests_per_minute
        self.refill_rate = self.requests_per_minute / 60.0
        self._ip_buckets: Dict[str, TokenBucket] = {}
        self._user_buckets: Dict[str, TokenBucket] = {}
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 300.0

    def _get_ip_bucket(self, client_ip: str) -> TokenBucket:
        if client_ip not in self._ip_buckets:
            self._ip_buckets[client_ip] = TokenBucket(
                capacity=self.capacity,
                refill_rate=self.refill_rate,
            )
        return self._ip_buckets[client_ip]

    def _get_user_bucket(self, user_id: str) -> TokenBucket:
        if user_id not in self._user_buckets:
            self._user_buckets[user_id] = TokenBucket(
                capacity=self.capacity,
                refill_rate=self.refill_rate,
            )
        return self._user_buckets[user_id]

    def _cleanup_stale_buckets(self) -> None:
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        stale_threshold = now - 600.0
        stale_ips = [
            ip for ip, bucket in self._ip_buckets.items()
            if bucket.last_refill < stale_threshold
        ]
        for ip in stale_ips:
            del self._ip_buckets[ip]
        stale_users = [
            uid for uid, bucket in self._user_buckets.items()
            if bucket.last_refill < stale_threshold
        ]
        for uid in stale_users:
            del self._user_buckets[uid]
        self._last_cleanup = now
        if stale_ips or stale_users:
            logger.debug(
                f"Rate limiter cleanup: removed {len(stale_ips)} IP buckets, "
                f"{len(stale_users)} user buckets"
            )

    def check_rate_limit(
        self, client_ip: str, user_id: Optional[str] = None
    ) -> Tuple[bool, float]:
        self._cleanup_stale_buckets()
        ip_bucket = self._get_ip_bucket(client_ip)
        if not ip_bucket.consume():
            return False, ip_bucket.retry_after()
        if user_id is not None:
            user_bucket = self._get_user_bucket(user_id)
            if not user_bucket.consume():
                return False, user_bucket.retry_after()
        return True, 0.0

    async def middleware(self, request: Request, call_next) -> Response:
        if request.url.path in ("/health", "/docs", "/redoc", "/openapi.json"):
            return await call_next(request)
        if request.method == "OPTIONS":
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        user_id = None
        auth_header = request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                from app.core.auth import decode_access_token, is_token_blacklisted
                token = auth_header[7:]
                if not is_token_blacklisted(token):
                    token_data = decode_access_token(token)
                    user_id = token_data.user_id
            except Exception:
                pass
        allowed, retry_after = self.check_rate_limit(client_ip, user_id)
        if not allowed:
            raise RateLimitExceededException(
                detail=f"Rate limit exceeded. Retry after {retry_after:.0f} seconds.",
                details={"retry_after_seconds": round(retry_after, 1)},
            )
        response = await call_next(request)
        return response


rate_limiter = RateLimiter()
