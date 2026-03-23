import logging
from functools import lru_cache
from pathlib import Path
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.constants import END, START
from langgraph.graph import MessagesState, StateGraph
from langgraph.prebuilt import ToolNode

# 1. 改为导入工厂函数，不要导入实例化的 llm
from app.agents.checkpointer import ensure_agent_checkpointer_sync, get_agent_checkpointer
from app.agents.llm_factory import get_llm
from app.agents.memory_store import (
    ensure_agent_memory_store_sync,
    get_agent_memory_store,
    init_agent_memory_store,
)
from app.agents.tools import TOOLS
from app.core.config import settings

# 缓存 Prompt 路径，但不要在顶层读取文件（避免磁盘 IO 延迟）
BASE_DIR = Path(__file__).resolve().parent
PROMPT_PATH = BASE_DIR / "prompts" / "tutor.md"


# ===== Helpers =====

@lru_cache(maxsize=1)
def get_cached_prompt() -> str:
    """封装 Prompt 读取，配合缓存实现懒加载"""
    with open(PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read()


@lru_cache(maxsize=1)
def get_llm_with_tools():
    base_llm = get_llm()
    return base_llm.bind_tools(TOOLS)


def _extract_user_query(messages: list[object]) -> Optional[str]:
    for message in reversed(messages):
        role = None
        content = None
        if hasattr(message, "type"):
            role = getattr(message, "type", None)
            content = getattr(message, "content", None)
        elif isinstance(message, dict):
            role = message.get("role")
            content = message.get("content")
        elif isinstance(message, (list, tuple)) and len(message) >= 2:
            role = message[0]
            content = message[1]

        if role in {"human", "user"} and isinstance(content, str) and content.strip():
            return content.strip()
    return None


def _is_session_start(messages: list[object]) -> bool:
    human_count = 0
    for message in messages:
        role = getattr(message, "type", None)
        if role is None and isinstance(message, dict):
            role = message.get("role")
        if role in {"human", "user"}:
            human_count += 1
    return human_count <= 1


def _memory_line_from_item(item: object) -> Optional[str]:
    value = getattr(item, "value", None) or {}
    data = value.get("data")
    if not data:
        return None

    category = value.get("category") or "note"
    trigger = value.get("trigger")
    stage = value.get("stage")
    tags = value.get("tags") or []
    created_at = value.get("created_at")

    extras: list[str] = [f"type={category}"]
    if trigger:
        extras.append(f"trigger={trigger}")
    if stage:
        extras.append(f"stage={stage}")
    if tags:
        extras.append(f"tags={','.join([str(tag) for tag in tags[:4]])}")
    if created_at:
        extras.append(f"time={created_at}")

    return f"- {'; '.join(extras)}\n  {str(data)}"


async def _build_memory_context(
        messages: list[object],
        user_id: Optional[str],
        unit_id: Optional[str],
) -> str:
    if not user_id:
        raise ValueError(
            "llm_call requires configurable.user_id for memory retrieval. "
            "For LangGraph Studio/dev runs, pass config.configurable.user_id."
        )
    if not unit_id:
        raise ValueError(
            "llm_call requires configurable.unit_id for memory retrieval. "
            "For LangGraph Studio/dev runs, pass config.configurable.unit_id."
        )

    query = _extract_user_query(messages)
    if not query:
        return ""

    store = get_agent_memory_store()
    namespace = (settings.REDIS_KEY_PREFIX, "memories", str(user_id), str(unit_id))
    lines: list[str] = []
    seen_lines: set[str] = set()

    queries = [query]
    if _is_session_start(messages):
        # 在每次会话开场追加一次通用学习画像检索，帮助模型快速恢复用户长期状态。
        queries.append("learning progress weaknesses preferences stage summary")

    for current_query in queries:
        try:
            memories = await store.asearch(namespace, query=current_query)
        except Exception:
            logging.exception(
                "Long-term memory search failed: user_id=%s unit_id=%s query=%s",
                user_id,
                unit_id,
                current_query,
            )
            raise

        for item in memories[:5]:
            line = _memory_line_from_item(item)
            if line and line not in seen_lines:
                seen_lines.add(line)
                lines.append(line)
            if len(lines) >= 8:
                break
        if len(lines) >= 8:
            break

    if not lines:
        return ""
    return "\n".join(lines)


# ===== Nodes =====

async def llm_call(state: MessagesState, config: RunnableConfig):
    """
    在这里才进行模型实例化和工具绑定。
    得益于 get_llm 的 lru_cache，只有第一次运行会慢，import 时瞬间完成。
    """
    # 动态获取并绑定工具
    llm_with_tools = get_llm_with_tools()

    # langgraph dev 直连运行时，lifespan 不会帮我们初始化 memory store。
    # 这里做一次按需初始化，避免 "Agent memory store is not initialized."。
    try:
        get_agent_memory_store()
    except RuntimeError:
        await init_agent_memory_store()

    # 构造消息
    system_prompt = get_cached_prompt()
    configurable = (config or {}).get("configurable") or {}
    logging.warning(
        "[llm_call.config] config=%r configurable_keys=%s configurable=%r",
        config,
        sorted(list(configurable.keys())),
        configurable,
    )
    user_id = configurable.get("user_id")
    unit_id = configurable.get("unit_id")
    if not user_id or not unit_id:
        logging.error(
            "Missing required configurable keys in llm_call: have_keys=%s",
            sorted(list(configurable.keys())),
        )
    memory_context = await _build_memory_context(state["messages"], user_id, unit_id)
    if memory_context:
        system_prompt = (
            f"{system_prompt}\n\n[Long-term memory]\n"
            f"[scope: unit={unit_id or 'global'}]\n{memory_context}"
        )
    messages = [SystemMessage(content=system_prompt)] + state["messages"]

    # 异步调用
    response = await llm_with_tools.ainvoke(
        messages,
        config=config
    )
    return {"messages": [response]}


# ===== Logic & Graph =====

def should_continue(state: MessagesState) -> Literal["tool_node", END]:
    last_message = state["messages"][-1]
    if getattr(last_message, "tool_calls", None):
        return "tool_node"
    return END


class GraphConfig(BaseModel):
    # 去掉 default，在 Studio UI 中它会标记为必填，不填无法运行
    user_id: str = Field(
        ...,
        description="用户的唯一标识符 (必填)"
    )
    unit_id: str = Field(
        ...,
        description="单元的唯一标识符 (必填)"
    )
    resource_ids: List[str] = Field(
        ...,
        description="资源的唯一标识符列表 (必填)"
    )

# 初始化时传入 schema
agent_builder = StateGraph(MessagesState, config_schema=GraphConfig)
# agent_builder = StateGraph(MessagesState)
agent_builder.add_node("llm_call", llm_call)
agent_builder.add_node("tool_node", ToolNode(TOOLS))
agent_builder.add_edge(START, "llm_call")
agent_builder.add_conditional_edges(
    "llm_call",
    should_continue,
    {"tool_node": "tool_node", END: END}  # 显式映射
)
agent_builder.add_edge("tool_node", "llm_call")


@lru_cache(maxsize=1)
def get_agent(with_checkpointer: bool = True):
    """Build compiled agent.

    - with_checkpointer=True: for app runtime memory persistence.
    - with_checkpointer=False: for LangGraph API/dev graph export.
    """
    if with_checkpointer:
        ensure_agent_memory_store_sync()
        ensure_agent_checkpointer_sync()
        return agent_builder.compile(checkpointer=get_agent_checkpointer())
    return agent_builder.compile()


# Export graph for langgraph dev/API without custom checkpointer.
agent = agent_builder.compile()
tutor = agent
