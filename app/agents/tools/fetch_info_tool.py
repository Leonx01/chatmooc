import asyncio
import logging
import time
from typing import Any

import pytest
from langchain.tools import ToolRuntime
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.core.milvus_core import vector_manager

logger = logging.getLogger(__name__)
EMBED_TIMEOUT_SEC = 45
SEARCH_TIMEOUT_SEC = 45


class FetchInfoInput(BaseModel):
    query: str = Field(description="Query to fetch info from")
    top_k: int = Field(default=5, ge=1, le=20, description="Top k results")


@tool("fetch_info", args_schema=FetchInfoInput)
async def fetch_info_tool(
    query: str,
    runtime: ToolRuntime,
    top_k: int = 5,
) -> dict[str, Any]:
    """
    Semantic Search & Technical Documentation Retrieval Tool.

    Purpose:
        Perform high-precision semantic searches across a vectorized technical knowledge base.
        This tool is designed to retrieve relevant excerpts from documentation, manuals,
        and historical technical logs based on a natural language query.

    How to use:
        - Provide a clear, standalone search query that encapsulates the core technical concept or problem.
        - The tool automatically restricts the search scope to the current user's authorized 'resource_ids'
          and performs multi-tenant safety verification via 'user_id' (both injected automatically).
        - Use this when the current conversation context is insufficient to answer technical questions
          or when specific, ground-truth documentation is required.

    Args:
        query (str): The natural language search string. Be specific (e.g., "Redis cluster rebalancing logic"
                     instead of "how to fix Redis").
        top_k (int, optional): The number of top relevant document chunks to return. Defaults to 5.

    Returns:
        dict: A structured response containing:
            - 'results': List of document segments with metadata (source, page, relevance score).
            - 'status': "success" or "failed".
            - 'count': Number of documents successfully retrieved.

    Notes:
        - If no relevant information is found, the tool returns an empty results list;
          use this as a signal to re-query or inform the user about the knowledge gap.
    """
    vector_store = vector_manager.store

    if vector_store is None:
        return {
            "status": "error",
            "message": "Knowledge base (Milvus) is not initialized.",
        }

    config = runtime.config or {}
    configurable = (config or {}).get("configurable") or {}
    context = runtime.context

    user_id = None
    resource_ids = None
    if isinstance(context, dict):
        user_id = context.get("user_id")
        resource_ids = context.get("resource_ids")
    else:
        user_id = getattr(context, "user_id", None)
        resource_ids = getattr(context, "resource_ids", None)

    if user_id is None:
        user_id = configurable.get("user_id")
    if resource_ids is None:
        resource_ids = configurable.get("resource_ids")
    if isinstance(resource_ids, list):
        # 清洗空字符串/空白项，避免构造异常 filter 表达式。
        resource_ids = [str(rid).strip() for rid in resource_ids if str(rid).strip()]

    logger.warning(
        "[fetch_info_tool.runtime] context=%r configurable_keys=%s resolved_user_id=%s resolved_resource_ids_count=%s",
        context,
        sorted(list(configurable.keys())),
        user_id,
        len(resource_ids) if isinstance(resource_ids, list) else None,
    )

    if not resource_ids or not user_id:
        return {
            "status": "failed",
            "message": "fetch_info_tool requires runtime.context/resource_ids and user_id.",
            "required_keys": ["resource_ids", "user_id"],
            "have_context_keys": (
                sorted(list(context.keys())) if isinstance(context, dict) else None
            ),
            "have_configurable_keys": sorted(list(configurable.keys())),
        }

    # 2️⃣ 安全地构建表达式
    # 确保 rid 被处理为字符串，防止注入或语法错误
    safe_ids = [f'"{str(rid)}"' for rid in resource_ids]
    filter_expr = f'resource_id in [{", ".join(safe_ids)}]'

    if user_id:
        filter_expr += f' and user_id == "{user_id}"'

    # 3️⃣ 执行检索（分阶段超时与耗时日志，定位到底卡在 embedding 还是 Milvus 检索）
    started = time.monotonic()
    logger.warning(
        "[fetch_info_tool.search_start] top_k=%s filter_expr=%s",
        top_k,
        filter_expr,
    )
    try:
        embed_started = time.monotonic()
        query_vector = await asyncio.wait_for(
            asyncio.to_thread(vector_store.embedding_func.embed_query, query),
            timeout=EMBED_TIMEOUT_SEC,
        )
        embed_elapsed = int((time.monotonic() - embed_started) * 1000)
        logger.warning("[fetch_info_tool.embed_done] elapsed_ms=%s", embed_elapsed)
    except asyncio.TimeoutError:
        total_elapsed = int((time.monotonic() - started) * 1000)
        return {
            "status": "error",
            "error_code": "embed_timeout",
            "message": (
                f"Embedding timeout after {EMBED_TIMEOUT_SEC}s. "
                f"elapsed_ms={total_elapsed}"
            ),
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "embed_failed",
            "message": f"Embedding failed: {str(e)}",
        }

    try:
        search_started = time.monotonic()
        docs_with_scores = await asyncio.wait_for(
            asyncio.to_thread(
                vector_store.similarity_search_with_score_by_vector,
                embedding=query_vector,
                k=top_k,
                expr=filter_expr,
            ),
            timeout=SEARCH_TIMEOUT_SEC,
        )
        search_elapsed = int((time.monotonic() - search_started) * 1000)
        logger.warning("[fetch_info_tool.search_done] elapsed_ms=%s", search_elapsed)
    except asyncio.TimeoutError:
        total_elapsed = int((time.monotonic() - started) * 1000)
        return {
            "status": "error",
            "error_code": "search_timeout",
            "message": (
                f"Milvus search timeout after {SEARCH_TIMEOUT_SEC}s. "
                f"elapsed_ms={total_elapsed}"
            ),
        }
    except Exception as e:
        return {
            "status": "error",
            "error_code": "search_failed",
            "message": f"Search failed: {str(e)}",
        }

    logger.warning(
        "[fetch_info_tool.total_done] elapsed_ms=%s results=%s",
        int((time.monotonic() - started) * 1000),
        len(docs_with_scores) if docs_with_scores else 0,
    )

    # 4️⃣ 结果封装
    if not docs_with_scores:
        return {"status": "success", "data": "未找到匹配的参考内容。", "count": 0}

    formatted_docs = []
    combined_texts = []
    for doc, score in docs_with_scores:
        formatted_docs.append(
            {
                "content": doc.page_content,
                "score": float(score),
                "metadata": doc.metadata,
            }
        )
        combined_texts.append(f"[匹配度: {score:.4f}]\n{doc.page_content}")

    return {
        "status": "success",
        "data": "\n\n---\n\n".join(combined_texts),
        "content": formatted_docs,  # 供内部逻辑使用的结构化数据
        "count": len(formatted_docs),
    }


# Test code below - normally in separate test file
@pytest.mark.asyncio  # 需要安装 pytest-asyncio 插件
async def test_fetch_info_logic():
    print("\n开始集成测试...")

    # 1. 测试懒加载
    assert vector_manager._store is None
    store = vector_manager.store
    assert store is not None

    # 2. 测试工具调用
    test_input = {"query": "测试查询", "top_k": 1}
    injected = {"resource_ids": ["test_res"], "user_id": "test_user"}

    result = await fetch_info_tool.ainvoke({**test_input, **injected})

    assert "status" in result
    print(f"测试完成，状态: {result['status']}")
