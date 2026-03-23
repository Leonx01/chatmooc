import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Dict

from langchain_anthropic import ChatAnthropic
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import LLMResult
from langchain_deepseek import ChatDeepSeek
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from load_dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


# =========================
# Data structures
# =========================
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


# =========================
# 1. 计量回调处理器 (LangChain 正统做法)
# =========================
class MeteringCallbackHandler(BaseCallbackHandler):
    """通过回调机制在底层监听 LLM 的结束事件，无侵入提取 Token 并计算成本"""

    def __init__(self, name: str, pricing: Pricing, log: logging.Logger = logger):
        self.name = name
        self.pricing = pricing
        self._log = log

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        prompt_tokens = 0
        completion_tokens = 0

        # 策略 1: 尝试从最外层的 llm_output 提取 (兼容大部分老版本和非流式 OpenAI)
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)

        # 策略 2: 如果策略 1 失败，尝试从 message 内部提取
        if prompt_tokens == 0 and completion_tokens == 0:
            try:
                message = response.generations[0][0].message

                # 使用 getattr 绕过 IDE 的静态类型检查警告
                usage_metadata = getattr(message, "usage_metadata", None)

                if usage_metadata:
                    # LangChain v0.2+ 的标准写法
                    prompt_tokens = usage_metadata.get("input_tokens", 0)
                    completion_tokens = usage_metadata.get("output_tokens", 0)
                else:
                    # 策略 3: 兜底处理部分把 usage 塞进 additional_kwargs 的偏门模型 (如早期 Anthropic)
                    additional_kwargs = getattr(message, "additional_kwargs", {})
                    token_usage = additional_kwargs.get("token_usage", {})
                    # 某些模型可能用 input_tokens，有些用 prompt_tokens，做个兼容
                    prompt_tokens = token_usage.get("prompt_tokens") or token_usage.get(
                        "input_tokens", 0
                    )
                    completion_tokens = token_usage.get(
                        "completion_tokens"
                    ) or token_usage.get("output_tokens", 0)
            except (IndexError, AttributeError):
                pass

        total_tokens = prompt_tokens + completion_tokens

        # 如果毫无消耗（可能是纯流式未开启 include_usage，或模型不支持），直接跳过日志
        if total_tokens == 0:
            return

        # 计算费用
        cost_prompt = (prompt_tokens / 1000.0) * self.pricing.prompt_per_1k
        cost_completion = (completion_tokens / 1000.0) * self.pricing.completion_per_1k
        total_cost = cost_prompt + cost_completion

        self._log.info(
            "LLM usage | name=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s cost=%.6f",
            self.name,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            total_cost,
        )


# =========================
# 2. 注册表 (去掉繁琐的闭包，只留核心元数据)
# =========================
MODEL_REGISTRY: Dict[str, LLMConfig] = {
    "deepseek": LLMConfig(
        model_class=ChatDeepSeek,
        model_name=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        env_prefix="DEEPSEEK",
        pricing=Pricing(prompt_per_1k=0.14, completion_per_1k=0.28),
    ),
    "gpt-4o-mini": LLMConfig(
        model_class=ChatOpenAI,
        model_name=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        env_prefix="OPENAI",
        pricing=Pricing(prompt_per_1k=0.15, completion_per_1k=0.6),
    ),
    "claude-3-5-sonnet": LLMConfig(
        model_class=ChatAnthropic,
        model_name=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
        env_prefix="ANTHROPIC",
        pricing=Pricing(prompt_per_1k=3.0, completion_per_1k=15.0),
    ),
    "ollama": LLMConfig(
        model_class=ChatOllama,
        model_name=os.getenv("OLLAMA_MODEL", "llama3.1"),
        env_prefix="OLLAMA",
        pricing=Pricing(prompt_per_1k=0.0, completion_per_1k=0.0),
    ),
}

DEFAULT_LLM_NAME = os.getenv("LLM_NAME", "deepseek").lower()


def available_llms() -> list[str]:
    return sorted(MODEL_REGISTRY.keys())


# =========================
# 3. 优雅的工厂方法
# =========================
@lru_cache(maxsize=8)
def get_llm(name: str | None = None, temperature: float = 0.0) -> BaseChatModel:
    target = (name or DEFAULT_LLM_NAME).lower()
    if target not in MODEL_REGISTRY:
        raise KeyError(
            f"Unknown LLM '{target}'. Available: {', '.join(available_llms())}"
        )

    cfg = MODEL_REGISTRY[target]

    # 动态组装参数：剔除空值，避免覆盖 LangChain 默认逻辑
    kwargs = {"model": cfg.model_name, "temperature": temperature}

    api_key = os.getenv(f"{cfg.env_prefix}_API_KEY")
    if api_key:
        kwargs["api_key"] = api_key

    base_url = os.getenv(f"{cfg.env_prefix}_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url

    # 实例化原生模型
    base_llm = cfg.model_class(**kwargs)

    # 重点：将计费回调注入到模型的 Runnable 配置中
    # 这样返回的依然是 BaseChatModel，你可以随意 bind_tools() 或者 stream()
    metering_callback = MeteringCallbackHandler(
        name=target, pricing=cfg.pricing, log=logger
    )
    return base_llm.with_config(callbacks=[metering_callback])


class _LazyLLM:
    """Defer LLM construction until first use to keep module imports fast."""

    def __init__(self, factory: Callable[[], BaseChatModel]):
        self._factory = factory
        self._instance: BaseChatModel | None = None

    def _get(self) -> BaseChatModel:
        if self._instance is None:
            self._instance = self._factory()
        return self._instance

    def __getattr__(self, name: str):
        return getattr(self._get(), name)

    def __call__(self, *args, **kwargs):
        return self._get()(*args, **kwargs)


# Backwards-compatible default export (lazy)
llm = _LazyLLM(get_llm)
