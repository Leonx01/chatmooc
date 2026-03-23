from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional, Union

from langgraph.store.redis.aio import AsyncRedisStore

from app.core.config import settings

try:
    from langgraph.store.memory import InMemoryStore
except ImportError:
    InMemoryStore = None

logger = logging.getLogger(__name__)

MemoryStore = (
    AsyncRedisStore if InMemoryStore is None else Union[AsyncRedisStore, InMemoryStore]
)
_agent_memory_store: Optional[MemoryStore] = None
_agent_memory_store_cm: Optional[Any] = None


def _resolve_redis_url() -> str:
    redis_url = (settings.REDIS_URL or "").strip()
    if redis_url:
        return redis_url

    password = (settings.REDIS_PASSWORD or "").strip()
    auth = f":{password}@" if password else ""
    return (
        f"redis://{auth}{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
    )


def get_agent_memory_store():
    """Return initialized memory store instance."""
    if _agent_memory_store is None:
        raise RuntimeError("Agent memory store is not initialized.")
    return _agent_memory_store


def ensure_agent_memory_store_sync():
    """Ensure memory store initialized in sync contexts (e.g. langgraph dev import)."""
    global _agent_memory_store
    if _agent_memory_store is not None:
        return _agent_memory_store

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # No running loop: safe to bootstrap here for module-import workflows.
        return asyncio.run(init_agent_memory_store())

    raise RuntimeError(
        "Agent memory store is not initialized in this event loop. "
        "Call `await init_agent_memory_store()` first."
    )


async def init_agent_memory_store():
    """Initialize shared memory store (AsyncRedisStore first, in-memory fallback)."""
    global _agent_memory_store, _agent_memory_store_cm
    if _agent_memory_store is not None:
        return _agent_memory_store

    redis_url = _resolve_redis_url()
    try:
        candidate = AsyncRedisStore.from_conn_string(redis_url)
        if hasattr(candidate, "__aenter__") and hasattr(candidate, "__aexit__"):
            _agent_memory_store_cm = candidate
            store = await _agent_memory_store_cm.__aenter__()
        else:
            store = candidate
            if hasattr(store, "asetup"):
                await store.asetup()
        logger.info("LangGraph memory store initialized with Redis: %s", redis_url)
        _agent_memory_store = store
    except Exception as exc:
        if InMemoryStore is None:
            logger.error(
                "Redis memory store unavailable and InMemoryStore missing; cannot initialize: %s",
                exc,
                exc_info=True,
            )
            raise
        logger.warning(
            "Redis memory store unavailable; fallback to InMemoryStore (no persistence): %s",
            exc,
        )
        _agent_memory_store = InMemoryStore()

    return _agent_memory_store


async def close_agent_memory_store() -> None:
    """Close memory store resources when app shuts down."""
    global _agent_memory_store, _agent_memory_store_cm
    store = _agent_memory_store
    store_cm = _agent_memory_store_cm
    _agent_memory_store = None
    _agent_memory_store_cm = None

    if store_cm is not None:
        try:
            await store_cm.__aexit__(None, None, None)
        except Exception:
            logger.exception("Failed to close AsyncRedisStore context manager cleanly.")
        return

    if isinstance(store, AsyncRedisStore):
        try:
            await store.__aexit__(None, None, None)
        except Exception:
            logger.exception("Failed to close AsyncRedisStore cleanly.")
