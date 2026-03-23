import logging

from fastapi import HTTPException, Request, status

from app.core.redis_core import redis_client

logger = logging.getLogger(__name__)


async def rate_limiter(
    request: Request,
    # 你可以根据需要调整这里的默认值
    capacity: int = 10,
    rate: float = 2.0,
    prefix: str = "default",
):
    # 根据用户 IP 作为唯一标识
    user_id = request.client.host if request.client else "unknown"
    bucket_id = f"{prefix}:{user_id}"

    # 调用你的 RedisClient 实例
    try:
        result = await redis_client.acquire_tokens(
            bucket_id=bucket_id, capacity=capacity, refill_rate=rate
        )
    except Exception as exc:
        # Fail-open: 当 Redis 不可用时，避免核心业务接口完全不可用。
        logger.warning("Rate limiter degraded because redis is unavailable: %s", exc)
        request.state.remaining = None
        return

    if not result["allowed"]:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"msg": "请求过于频繁", "remaining": result["remaining"]},
        )

    # 也可以把剩余量塞进 request 供后续 Header 使用
    request.state.remaining = result["remaining"]
