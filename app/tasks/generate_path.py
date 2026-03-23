from __future__ import annotations

import logging

from app.core.celery_core import celery_app

logger = logging.getLogger("chatmooc.celery.generate_path")


@celery_app.task(name="chatmooc.generate_path", bind=True)
def generate_path_task(self, payload: dict) -> dict:
    pass
