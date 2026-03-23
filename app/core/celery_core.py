from __future__ import annotations

import asyncio
import os

from celery import Celery

from app.core.config import settings

if os.name == "nt":
    # asyncmy + ProactorEventLoop 在 Windows 下偶发连接写入异常，
    # Worker 使用 Selector 策略更稳定。
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


celery_app = Celery(
    "chatmooc",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_default_queue=settings.RESOURCE_PARSE_QUEUE,
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    imports=(
        "app.tasks.parse_resource",
        "app.tasks.generate_path",
    ),
    # Keep prefetch small so one long PDF doesn't starve other tasks.
    worker_prefetch_multiplier=1,
    # At-least-once delivery: ack after task execution completes.
    task_acks_late=True,
    # If worker process is lost, reject and requeue instead of implicit ack.
    task_reject_on_worker_lost=True,
    # Do not ack failed/timeout tasks; allow redelivery with retry policy.
    task_acks_on_failure_or_timeout=False,
)

# Windows compatibility:
# `billiard` prefork/spawn workers may hit WinError 5 (Access is denied).
# Use solo pool to keep worker stable on local Windows dev.
if os.name == "nt":
    celery_app.conf.update(
        worker_pool="solo",
        worker_concurrency=1,
    )
