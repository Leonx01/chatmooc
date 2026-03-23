from __future__ import annotations

import operator
from pathlib import Path
from typing import Annotated, Any, Literal, TypedDict

from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.utils.json import parse_json_markdown
from langgraph.constants import END, START
from langgraph.graph import StateGraph
from langgraph.types import Send

from app.agents.llm_factory import llm
from app.agents.tools.fetch_info_tool import fetch_info_tool

TOOLS = [fetch_info_tool]

class Unit(TypedDict):
    id: str  # Format: unit_n
    title: str  # Unit name
    description: str  # One-sentence summary of the core content
    core_concepts: list[str]  # 2-5 concepts
    goal: str  # The verifiable ability achieved after completing this unit
    order: int  # Incremental integer


class CompletedUnit(TypedDict):
    id: str
    order: int
    title: str
    content: str  # Markdown lesson plan


class State(TypedDict):
    # Inputs
    sid: str
    resource: str
    level: Literal["Easy", "Medium", "Hard"] | str

    # Planner output
    introduction: str
    units: list[Unit]

    # Parallel aggregation from workers
    completed_units: Annotated[list[CompletedUnit], operator.add]

    # Final output
    final_lesson_plan: str


class WorkerState(TypedDict):
    unit: Unit
    completed_units: Annotated[list[CompletedUnit], operator.add]


BASE_DIR = Path(__file__).resolve().parent
PLANNER_PROMPT_PATH = BASE_DIR / "prompts" / "planner_en.md"
EXECUTOR_PROMPT_PATH = BASE_DIR / "prompts" / "executor_en.md"


def load_prompt(filepath: Path) -> str:
    # 读取本地文件通常很快，保留同步读取即可，如果是在高并发场景下可替换为 aiofiles
    return filepath.read_text(encoding="utf-8")


def _normalize_plan(plan: dict[str, Any]) -> tuple[str, list[Unit]]:
    introduction = str(plan.get("introduction", "")).strip()
    units_raw = plan.get("units", [])
    if not isinstance(units_raw, list):
        units_raw = []

    units: list[Unit] = []
    for idx, item in enumerate(units_raw, start=1):
        if not isinstance(item, dict):
            continue

        unit_id = str(item.get("id") or f"unit_{idx}").strip()
        title = str(item.get("title", "")).strip() or unit_id
        description = str(item.get("description", "")).strip()
        goal = str(item.get("goal", "")).strip()

        core_concepts = item.get("core_concepts", [])
        if not isinstance(core_concepts, list):
            core_concepts = []
        core_concepts = [str(x).strip() for x in core_concepts if str(x).strip()]

        order = item.get("order", idx)
        try:
            order_int = int(order)
        except Exception:
            order_int = idx
        units.append(
            Unit(
                id=unit_id,
                title=title,
                description=description,
                core_concepts=core_concepts,
                goal=goal,
                order=order_int,
            )
        )

    units.sort(key=lambda u: u["order"])
    return introduction, units


async def planner_node(state: State) -> dict[str, Any]:
    """Planner: return introduction + units[] in the schema from planner_en.md."""

    resource = state.get("resource") or state.get("topic")  # type: ignore[typeddict-item]
    level = state.get("level", "Easy")

    system_prompt = load_prompt(PLANNER_PROMPT_PATH)
    user_prompt = f"**Resource**:\n{resource}\n\n**Level**:\n{level}"

    # 修改 1: 使用 ainvoke 异步调用 LLM
    resp = await llm.ainvoke([SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)])
    parsed = parse_json_markdown(resp.content)
    introduction, units = _normalize_plan(parsed if isinstance(parsed, dict) else {})
    return {"introduction": introduction, "units": units}


def assign_workers(state: State):
    """Fan-out: one executor per unit (runs in parallel)."""
    # 纯逻辑函数（无 I/O）可以继续保持同步 def，LangGraph 会自动处理
    units = sorted(state["units"], key=lambda u: u["order"])
    return [Send("executor", {"unit": u}) for u in units]


async def executor_node(state: WorkerState) -> dict[str, Any]:
    """Executor: generate a Markdown 5E lesson plan for one unit (tool-call loop supported)."""

    unit = state["unit"]

    tools_by_name = {tool.name: tool for tool in TOOLS}
    llm_with_tools = llm.bind_tools(TOOLS)

    messages: list[Any] = [
        SystemMessage(content=load_prompt(EXECUTOR_PROMPT_PATH)),
        HumanMessage(content=f"{unit}"),
    ]

    for _ in range(8):
        # 修改 2: 异步调用带 Tool 的 LLM
        ai_msg = await llm_with_tools.ainvoke(messages)
        messages.append(ai_msg)

        tool_calls = getattr(ai_msg, "tool_calls", None) or []
        if not tool_calls:
            break

        for tool_call in tool_calls:
            tool = tools_by_name.get(tool_call.get("name", ""))
            if tool is None:
                observation = f"Tool not found: {tool_call.get('name')}"
            else:
                # 修改 3: 异步调用 Tool
                observation = await tool.ainvoke(tool_call.get("args", {}))
            messages.append(ToolMessage(content=str(observation), tool_call_id=tool_call["id"]))

    final_text = ""
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if isinstance(content, str) and content.strip():
            final_text = content.strip()
            break

    return {
        "completed_units": [
            {
                "id": unit["id"],
                "order": unit["order"],
                "title": unit["title"],
                "content": final_text,
            }
        ]
    }


async def synthesizer_node(state: State) -> dict[str, Any]:
    """Fan-in: order by `order` and merge into the final lesson plan Markdown."""
    # 虽然这里只有纯逻辑运算，但定义为 async 可以保持 Node 签名风格一致
    intro = (state.get("introduction") or "").strip()
    completed = state.get("completed_units", [])
    completed_sorted = sorted(
        [c for c in completed if isinstance(c, dict)],
        key=lambda c: int(c.get("order", 10**9)),
    )
    body = "\n\n---\n\n".join(
        str(c.get("content", "")).strip()
        for c in completed_sorted
        if str(c.get("content", "")).strip()
    )

    if intro and body:
        final = f"# Learning Path Introduction\n\n{intro}\n\n---\n\n{body}"
    elif intro:
        final = f"# Learning Path Introduction\n\n{intro}"
    else:
        final = body

    return {"final_lesson_plan": final}


# ===== Build Workflow =====
builder = StateGraph(State)
builder.add_node("planner", planner_node)
builder.add_node("executor", executor_node)
builder.add_node("synthesizer", synthesizer_node)

builder.add_edge(START, "planner")
builder.add_conditional_edges("planner", assign_workers, ["executor"])
builder.add_edge("executor", "synthesizer")
builder.add_edge("synthesizer", END)

graph = builder.compile()