import json
from functools import partial
from pathlib import Path
from typing import AsyncGenerator, Optional
import uuid

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

# 假设你的 agent 定义在 app.agents.tutor
from app.agents.tutor_agent import get_agent
from app.api.deps import rate_limiter
from app.api.v1.routes.auth import get_current_user
from app.models import Users

router = APIRouter(prefix="/chat", tags=["AI Chat"])
DEBUG_PAGE_PATH = Path(__file__).resolve().parents[4] / "scripts" / "chat_stream_test.html"

# 定义限流策略：AI 接口通常消耗资源较多，设置每秒 1 个，桶容量 3
chat_limit = partial(rate_limiter, capacity=3, rate=1.0, prefix="ai_chat")

# --- SSE Generator ---
class ChatRequest(BaseModel):
    message: str
    unit_id: Optional[str] = None
    session_id: Optional[str] = None
    resource_ids: list[str] = Field(default_factory=list)
    verbose_events: bool = False


def _to_json_text(payload: object) -> str:
    """Best-effort JSON serialization for LangGraph stream events."""
    encoded = jsonable_encoder(payload)
    return json.dumps(encoded, ensure_ascii=False, default=str)


def _sse(event_name: str, payload: object) -> str:
    return f"event: {event_name}\ndata: {_to_json_text(payload)}\n\n"


def _detect_event_source(event: dict) -> str:
    """Classify event origin: agent | tool."""
    event_type = str(event.get("event", ""))
    metadata = event.get("metadata") or {}
    graph_node = str(metadata.get("langgraph_node", ""))

    if event_type.startswith("on_tool_"):
        return "tool"
    if graph_node == "tool_node":
        return "tool"
    return "agent"


async def langgraph_sse_generator(
    request_data: ChatRequest,
    user: Users,
) -> AsyncGenerator[str, None]:
    """
    核心生成器：将 LangGraph 的 astream 转换为 SSE 格式
    """

    # resource id 需要查库，建议用redis缓存住
    # 关键：这里将 unit_id 和 user_id 注入到 LangGraph 的系统 Config 中
    if not request_data.unit_id:
        yield _sse(
            "error",
            {
                "error": "unit_id is required",
                "error_type": "ValidationError",
            },
        )
        return

    if not request_data.resource_ids:
        yield _sse(
            "error",
            {
                "error": "resource_ids is required",
                "error_type": "ValidationError",
            },
        )
        return

    thread_id = request_data.session_id or str(uuid.uuid4())
    config = {
        "configurable": {
            "thread_id": thread_id,
            "unit_id": request_data.unit_id,
            "resource_ids": request_data.resource_ids,
            "user_id": str(user.uid),
        }
    }

    inputs = {"messages": [("user", request_data.message)]}

    try:
        # 发一个会话开始事件，前端可以据此初始化 UI 状态
        yield _sse(
            "status",
            {
                "stage": "session_start",
                "thread_id": thread_id,
                "unit_id": request_data.unit_id,
                "message": "会话已开始（记忆将绑定到当前 unit_id）",
            },
        )

        runtime_agent = get_agent()
        # 使用 astream_events(version="v2") 获取更细粒度事件
        async for event in runtime_agent.astream_events(inputs, config=config, version="v2"):
            event_type = str(event.get("event", ""))
            event_name = str(event.get("name", ""))
            event_data = event.get("data", {})
            source = _detect_event_source(event)

            if event_type == "on_tool_start":
                # 工具开始：前端可展示“正在使用 xxx 工具”
                yield _sse(
                    "status",
                    {
                        "source": "tool",
                        "stage": "tool_start",
                        "tool_name": event_name,
                        "message": f"正在使用 {event_name} 工具",
                        "input": event_data.get("input"),
                    },
                )
                continue

            if event_type == "on_tool_end":
                # 工具结束：可用于关闭 loading 或展示工具结果摘要
                yield _sse(
                    "status",
                    {
                        "source": "tool",
                        "stage": "tool_end",
                        "tool_name": event_name,
                        "message": f"{event_name} 工具执行完成",
                        "output": event_data.get("output"),
                    },
                )
                continue

            if event_type == "on_chat_model_stream":
                chunk = event_data.get("chunk")
                # 仅在有 token 文本时发送 token 事件，避免噪音
                text = getattr(chunk, "content", None) if chunk is not None else None
                if text and source == "agent":
                    yield _sse("token", {"source": source, "text": text})
                elif text and request_data.verbose_events:
                    # 工具内部若改为流式 LLM，这里可以看到其 token（默认关闭）
                    yield _sse("tool_token", {"source": source, "tool_name": event_name, "text": text})
                continue

            if event_type == "on_chat_model_end":
                # 提供结构化的最终模型输出，避免把整段内部运行上下文发给前端
                output = event_data.get("output")
                content = getattr(output, "content", None)
                if content and source == "agent":
                    yield _sse("message", {"source": source, "role": "assistant", "content": content})
                if request_data.verbose_events:
                    yield _sse("update", event)
                continue

            # 其他内部事件默认不推给前端，防止日志过大；
            # 若需要排障可通过 verbose_events=true 查看原始事件。
            if request_data.verbose_events:
                yield _sse("update", event)

        yield "event: end\ndata: [DONE]\n\n"

    except Exception as e:
        # 捕获异常并通知前端
        yield _sse(
            "error",
            {
                "error": str(e) or repr(e),
                "error_type": type(e).__name__,
            },
        )


# --- Router Endpoints ---

@router.get("/debug-page")
async def chat_debug_page():
    if not DEBUG_PAGE_PATH.exists():
        return {"error": f"debug page not found: {DEBUG_PAGE_PATH}"}
    return FileResponse(str(DEBUG_PAGE_PATH), media_type="text/html")

@router.post("/stream", dependencies=[Depends(chat_limit)])
async def chat_stream(
    request_data: ChatRequest,
    user: Users = Depends(get_current_user),
):
    """
    SSE 聊天接口，集成了：
    1. 频率限制 (chat_limit)
    2. LangGraph Config 注入
    3. 异步流式输出
    """
    return StreamingResponse(
        langgraph_sse_generator(request_data, user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream",
        }
    )
