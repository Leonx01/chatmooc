import asyncio
import logging
from sqlalchemy import select
from app.core.celery_core import celery_app
from app.core.mysql_core import db_manager
from app.models import Resources
from app.service.resource_service import ResourceService

_TASK_EVENT_LOOP: asyncio.AbstractEventLoop | None = None
logger = logging.getLogger(__name__)


def _get_task_event_loop() -> asyncio.AbstractEventLoop:
    """
    Reuse a single event loop in the worker process so async DB connections
    are not recycled across many short-lived loops on Windows.
    """
    global _TASK_EVENT_LOOP
    if _TASK_EVENT_LOOP is None or _TASK_EVENT_LOOP.is_closed():
        _TASK_EVENT_LOOP = asyncio.new_event_loop()
    return _TASK_EVENT_LOOP


async def _reset_resource_status_to_pending(rid: str) -> None:
    async with db_manager.get_session() as session:
        result = await session.execute(select(Resources).where(Resources.rid == rid))
        resource = result.scalar_one_or_none()
        if resource is None:
            return
        resource.status = 0  # pending
        await session.flush()

@celery_app.task(
    name="chatmooc.parse_resource",
    bind=True,
    autoretry_for=(ModuleNotFoundError, RuntimeError, ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def parse_resource_task(self, payload: dict) -> dict:
    rid = str(payload.get("rid", "")).strip()
    if not rid:
        raise ValueError("rid is required")

    # 定义内部异步逻辑
    async def run_logic():
        async with db_manager.get_session() as session:
            service = ResourceService(session)
            return await service.parse_resource_now(rid=rid)

    loop = _get_task_event_loop()
    try:
        result = loop.run_until_complete(run_logic())
    except Exception:
        # Any failure should release "parsing" lock so users can retry manually.
        try:
            loop.run_until_complete(_reset_resource_status_to_pending(rid))
        except Exception:
            logger.exception("Failed to reset resource status after parse error, rid=%s", rid)
        raise

    return {
        "task_id": self.request.id,
        **result,
    }