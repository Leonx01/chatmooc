"""Redis client with token bucket rate limiting helpers."""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

from redis.asyncio import Redis
from redis.exceptions import NoScriptError

from app.core.config import settings

_TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill_rate = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])
local ttl = tonumber(ARGV[5])

local tokens
local last
local data = redis.call('HMGET', key, 'tokens', 'timestamp')
if data[1] == false or data[1] == nil then
    tokens = capacity
else
    tokens = tonumber(data[1])
end
if data[2] == false or data[2] == nil then
    last = now
else
    last = tonumber(data[2])
end

local delta = math.max(0, now - last)
local refill = delta * refill_rate
tokens = math.min(capacity, tokens + refill)

local allowed = 0
if tokens >= requested then
    allowed = 1
    tokens = tokens - requested
end

redis.call('HMSET', key, 'tokens', tokens, 'timestamp', now)
if ttl > 0 then redis.call('EXPIRE', key, ttl) end

return {allowed, tokens}
"""


class RedisClient:
    def __init__(
        self,
        *,
        url: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        db: Optional[int] = None,
        password: Optional[str] = None,
        key_prefix: Optional[str] = None,
        default_capacity: Optional[int] = None,
        default_refill_rate: Optional[float] = None,
        default_ttl_seconds: Optional[int] = None,
    ) -> None:
        resolved_url = url or settings.REDIS_URL.strip()
        if resolved_url:
            self.url = resolved_url
        else:
            self.url = self._build_url(
                host or settings.REDIS_HOST,
                port or settings.REDIS_PORT,
                db if db is not None else settings.REDIS_DB,
                password or settings.REDIS_PASSWORD,
            )
        self.password = password or settings.REDIS_PASSWORD or None
        self.key_prefix = (key_prefix or settings.REDIS_KEY_PREFIX).rstrip(":")
        self.default_capacity = default_capacity or settings.RATE_LIMIT_CAPACITY
        self.default_refill_rate = (
            default_refill_rate or settings.RATE_LIMIT_REFILL_RATE
        )
        self.default_ttl_seconds = (
            default_ttl_seconds
            if default_ttl_seconds is not None
            else settings.RATE_LIMIT_TTL_SECONDS
        )

        self._redis: Optional[Redis] = None
        self._token_bucket_sha: Optional[str] = None

    @staticmethod
    def _build_url(host: str, port: int, db: int, password: str | None) -> str:
        auth = f":{password}@" if password else ""
        return f"redis://{auth}{host}:{port}/{db}"

    async def _get_client(self) -> Redis:
        if self._redis is None:
            self._redis = Redis.from_url(
                self.url, password=self.password, decode_responses=True
            )
        return self._redis

    def _bucket_key(self, bucket_id: str) -> str:
        return f"{self.key_prefix}:rate:{bucket_id}"

    async def _ensure_script(self) -> str:
        if self._token_bucket_sha is None:
            client = await self._get_client()
            self._token_bucket_sha = await client.script_load(_TOKEN_BUCKET_LUA)
        return self._token_bucket_sha

    async def acquire_tokens(
        self,
        bucket_id: str,
        *,
        tokens: int = 1,
        capacity: Optional[int] = None,
        refill_rate: Optional[float] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Consume tokens atomically using a token bucket.

        Returns a dict with ``allowed`` (bool) and ``remaining`` (float).
        """

        if tokens <= 0:
            raise ValueError("tokens must be positive")

        client = await self._get_client()
        sha = await self._ensure_script()

        now = time.time()
        cap = capacity or self.default_capacity
        rate = refill_rate or self.default_refill_rate
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_seconds

        if cap <= 0:
            raise ValueError("capacity must be positive")
        if rate <= 0:
            raise ValueError("refill_rate must be positive")
        if ttl < 0:
            raise ValueError("ttl_seconds cannot be negative")

        try:
            result = await client.evalsha(
                sha,
                1,
                self._bucket_key(bucket_id),
                now,
                cap,
                rate,
                tokens,
                ttl,
            )
        except NoScriptError:
            # Redis may have been restarted; reload the script and retry once.
            self._token_bucket_sha = await client.script_load(_TOKEN_BUCKET_LUA)
            result = await client.evalsha(
                self._token_bucket_sha,
                1,
                self._bucket_key(bucket_id),
                now,
                cap,
                rate,
                tokens,
                ttl,
            )

        allowed = bool(int(result[0]))
        remaining = float(result[1])
        return {"allowed": allowed, "remaining": remaining}

    async def get_bucket_state(self, bucket_id: str) -> Dict[str, float]:
        client = await self._get_client()
        key = self._bucket_key(bucket_id)
        data = await client.hgetall(key)
        if not data:
            return {"tokens": float(self.default_capacity), "timestamp": time.time()}
        return {
            "tokens": float(data.get("tokens", 0)),
            "timestamp": float(data.get("timestamp", 0)),
        }

    async def ping(self) -> bool:
        client = await self._get_client()
        return bool(await client.ping())

    async def warmup(self) -> None:
        """Prime the connection and Lua script so first request is fast."""
        client = await self._get_client()
        await client.ping()
        await self._ensure_script()

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.close()
            self._redis = None

    async def __aenter__(self) -> "RedisClient":
        await self._get_client()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()


# Shared instance for application usage
redis_client = RedisClient()

redis_client = RedisClient()
