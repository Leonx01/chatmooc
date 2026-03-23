from __future__ import annotations

import logging
import asyncio
from typing import Optional

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.redis.aio import AsyncRedisSaver

from app.core.config import settings

logger = logging.getLogger(__name__)

_agent_checkpointer: Optional[AsyncRedisSaver | InMemorySaver] = None


def _resolve_redis_url() -> str:
    redis_url = (settings.REDIS_URL or "").strip()
    if redis_url:
        return redis_url

    password = (settings.REDIS_PASSWORD or "").strip()
    auth = f":{password}@" if password else ""
    return f"redis://{auth}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"


def get_agent_checkpointer():
    """Return initialized checkpointer instance."""
    if _agent_checkpointer is None:
        raise RuntimeError("Agent checkpointer is not initialized.")
    return _agent_checkpointer


def ensure_agent_checkpointer_sync():
    """Ensure checkpointer initialized in sync contexts (e.g. langgraph dev import)."""
    global _agent_checkpointer
    if _agent_checkpointer is not None:
        return _agent_checkpointer

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop: safe to bootstrap here for module-import workflows.
        return asyncio.run(init_agent_checkpointer())

    raise RuntimeError(
        "Agent checkpointer is not initialized in this event loop. "
        "Call `await init_agent_checkpointer()` first."
    )


async def init_agent_checkpointer():
    """Initialize shared checkpointer (AsyncRedisSaver first, in-memory fallback)."""
    global _agent_checkpointer
    if _agent_checkpointer is not None:
        return _agent_checkpointer

    redis_url = _resolve_redis_url()
    try:
        saver = AsyncRedisSaver(redis_url=redis_url)
        await saver.asetup()
        logger.info("LangGraph checkpointer initialized with Redis: %s", redis_url)
        _agent_checkpointer = saver
    except Exception as exc:
        logger.warning(
            "Redis checkpointer unavailable (requires Redis Stack modules FT/JSON), fallback to InMemorySaver: %s",
            exc,
        )
        _agent_checkpointer = InMemorySaver()

    return _agent_checkpointer


async def close_agent_checkpointer() -> None:
    """Close checkpointer resources when app shuts down."""
    global _agent_checkpointer
    saver = _agent_checkpointer
    _agent_checkpointer = None

    if isinstance(saver, AsyncRedisSaver):
        try:
            await saver.__aexit__(None, None, None)
        except Exception:
            logger.exception("Failed to close AsyncRedisSaver cleanly.")
