import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.agents.checkpointer import close_agent_checkpointer, init_agent_checkpointer
from app.agents.memory_store import close_agent_memory_store, init_agent_memory_store
from app.agents.tutor_agent import get_agent
from app.api.v1.router import api_router
from app.core.celery_core import celery_app
from app.core.config import settings
from app.core.storage import resolve_local_parsed_dir, resolve_local_storage_dir

logger = logging.getLogger("chatmooc.app")

# This line initializes the metrics and exposes the /metrics endpoint


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- 2. Redis 预热（可选，但能避免首个请求时加载脚本的延迟）---
    # await redis_client.warmup()
    await init_agent_checkpointer()
    await init_agent_memory_store()
    get_agent.cache_clear()
    get_agent()

    # --- 3. Celery 预热逻辑 ---
    def _warmup_celery() -> bool:
        try:
            # 建立连接并放入池中，不直接 release 可能会更好，
            # 或者简单的确认 broker 是否存活
            with celery_app.connection_for_write() as conn:
                conn.ensure_connection(max_retries=2)
            return True
        except Exception as e:
            print(f"Celery warm up failed: {e}")
            return False

    # 使用 to_thread 处理同步阻塞调用
    success = await asyncio.to_thread(_warmup_celery)

    if not success:
        # 这里可以根据需求决定是否 raise RuntimeError("Broker unreachable")
        pass

    try:
        yield
    finally:
        await close_agent_checkpointer()
        await close_agent_memory_store()
        # --- 4. 资源清理 ---
        # 如果有数据库连接池（如 SQLAlchemy 或 Motor），在这里关闭
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        lifespan=lifespan,
    )
    if settings.STORAGE_BACKEND.lower() == "local":
        storage_dir = resolve_local_storage_dir()
        app.mount("/files", StaticFiles(directory=str(storage_dir)), name="files")
        parsed_dir = resolve_local_parsed_dir()
        app.mount("/parsed", StaticFiles(directory=str(parsed_dir)), name="parsed")
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    return app


app = create_app()
Instrumentator().instrument(app).expose(app)
