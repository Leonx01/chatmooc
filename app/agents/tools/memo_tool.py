import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, List, Literal

from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.agents.memory_store import get_agent_memory_store
from app.core.config import settings

logger = logging.getLogger(__name__)


class MemoInput(BaseModel):
    summary: str = Field(..., min_length=1, description="Concise long-term memory summary.")
    category: Literal["progress", "gap", "preference", "note"] = Field(
        default="progress",
        description="Memory type for retrieval routing.",
    )
    trigger: Literal["stage_complete", "learner_gap", "user_preference", "general_note"] = Field(
        default="general_note",
        description="Why this memory is written now.",
    )
    stage: Optional[str] = Field(
        default=None,
        description="Optional learning stage identifier, e.g. Stage 2 / 基础概念.",
    )
    tags: Optional[List[str]] = Field(default=None, description="Optional tags for retrieval.")


@tool("memo_tool", args_schema=MemoInput)
async def memo_tool(
    summary: str,
    runtime: ToolRuntime,
    category: Literal["progress", "gap", "preference", "note"] = "progress",
    trigger: Literal["stage_complete", "learner_gap", "user_preference", "general_note"] = "general_note",
    stage: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> dict[str, Any]:
    """
    Store long-term learning memories.

    Use this when a learning stage is completed, or when you identify a learner's gap.
    Summaries should be short, specific, and reusable (e.g., "User struggles with
    configuring Redis TTL; needs examples.").
    """
    cleaned = summary.strip()
    if not cleaned:
        return {"status": "failed", "message": "summary cannot be empty"}
    config = runtime.config or {}
    configurable = (config or {}).get("configurable") or {}
    context = runtime.context
    logger.warning(
        "[memo_tool.runtime] context=%r configurable_keys=%s",
        context,
        sorted(list(configurable.keys())),
    )
    if isinstance(context, dict):
        unit_id = context.get("unit_id")
        user_id = context.get("user_id")
    else:
        unit_id = getattr(context, "unit_id", None)
        user_id = getattr(context, "user_id", None)

    if unit_id is None:
        unit_id = configurable.get("unit_id")
    if user_id is None:
        user_id = configurable.get("user_id")

    if not unit_id:
        return {
            "status": "failed",
            "message": "memo_tool requires runtime.context.unit_id.",
            "required_keys": ["unit_id"],
            "have_context_keys": sorted(list(context.keys())) if isinstance(context, dict) else None,
            "have_configurable_keys": sorted(list(configurable.keys())),
        }
    if not user_id:
        return {
            "status": "failed",
            "message": "memo_tool requires runtime.context.user_id.",
            "required_keys": ["user_id"],
            "have_context_keys": sorted(list(context.keys())) if isinstance(context, dict) else None,
            "have_configurable_keys": sorted(list(configurable.keys())),
        }
    store = runtime.store if runtime.store is not None else get_agent_memory_store()
    namespace = (settings.REDIS_KEY_PREFIX, "memories", str(user_id), str(unit_id))
    payload = {
        "data": cleaned,
        "category": category,
        "trigger": trigger,
        "stage": stage.strip() if isinstance(stage, str) and stage.strip() else None,
        "tags": tags or [],
        "unit_id": str(unit_id),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await store.aput(namespace, str(uuid.uuid4()), payload)
    logger.info("memo_tool stored memory: user_id=%s unit_id=%s category=%s trigger=%s", user_id, unit_id, category, trigger)
    return {"status": "success", "stored": True}
