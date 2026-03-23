import logging
from dataclasses import dataclass
from typing import Any, Callable

import tiktoken
from langchain.agents.middleware import AgentMiddleware, ModelRequest, ModelResponse
from langchain_core.messages import get_buffer_string


@dataclass(frozen=True)
class Pricing:
    """Price per 1K tokens."""

    prompt_per_1k: float = 0.0
    completion_per_1k: float = 0.0


@dataclass(frozen=True)
class LLMConfig:
    model_class: Any  # 对应的 LangChain 模型类
    model_name: str  # 模型名称
    env_prefix: str  # 环境变量前缀 (例如 OPENAI, DEEPSEEK)
    pricing: Pricing = Pricing()


def count_tokens_with_tiktoken(
    text_or_messages: Any, model_name: str = "gpt-4o"
) -> int:
    """使用 tiktoken 计算 token 数量"""
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    if isinstance(text_or_messages, str):
        return len(encoding.encode(text_or_messages))

    if isinstance(text_or_messages, list):
        # 简单转换：将消息列表转为字符串（忽略角色 overhead 的极简版）
        # 生产环境建议参考 OpenAI Cookbook 的精确消息计数逻辑
        return len(encoding.encode(get_buffer_string(text_or_messages)))

    return 0


class TiktokenMeteringMiddleware(AgentMiddleware):
    def __init__(self, name: str, config: LLMConfig):
        super().__init__()
        self.name = name
        self.config = config

    def wrap_model_call(
        self, request: ModelRequest, handler: Callable[[ModelRequest], ModelResponse]
    ) -> ModelResponse:
        # --- [1. 请求前：计算 Prompt Tokens] ---
        # request.messages 是当前的上下文消息列表
        prompt_tokens = count_tokens_with_tiktoken(
            request.messages, model_name=self.config.model_name
        )

        # --- [2. 执行模型调用] ---
        response = handler(request)

        # --- [3. 请求后：计算 Completion Tokens] ---
        # response.result 通常是 AIMessage
        completion_text = (
            response.result.content if hasattr(response.result, "content") else ""
        )
        completion_tokens = count_tokens_with_tiktoken(
            completion_text, model_name=self.config.model_name
        )

        # --- [4. 成本计算与日志] ---
        total_tokens = prompt_tokens + completion_tokens
        cost = (
            prompt_tokens / 1000 * self.config.pricing.prompt_per_1k
            + completion_tokens / 1000 * self.config.pricing.completion_per_1k
        )

        logging.info(
            f"Middleware(Tiktoken) | {self.name} | "
            f"Prompt: {prompt_tokens}, Completion: {completion_tokens}, "
            f"Total: {total_tokens} | Cost: ${cost:.6f}"
        )

        return response
