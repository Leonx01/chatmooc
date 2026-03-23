import json
from json import JSONDecodeError
from pathlib import Path
from typing import Union

from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator

# 1. 关键：导入工厂函数，切断 import 时的实例化链条
from app.agents.llm_factory import get_llm

# ===== 路径配置 =====
BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_PATH = BASE_DIR / "prompts" / "flashcards.md"


def get_flashcard_prompt() -> str:
    """懒加载 Prompt，避免 import 时进行 IO 操作"""
    global _FLASHCARD_PROMPT
    if "_FLASHCARD_PROMPT" not in globals():
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            _FLASHCARD_PROMPT = f.read()
    return _FLASHCARD_PROMPT


# ===== 输入 Schema =====
class FlashcardInput(BaseModel):
    information: str = Field(..., description="学习内容")
    count: int = Field(default=3, description="闪卡数量（3-5）")

    @field_validator("count")
    @classmethod
    def validate_count(cls, v):
        return max(3, min(5, v))


# ===== Tool =====
@tool("flashcards_generate_tool", args_schema=FlashcardInput)
async def flashcards_generate_tool(
    information: str,
    count: int = 3,
) -> Union[str, dict]:
    """
    Extracts key concepts and facts from a source text to create study flashcards.

    This tool distills raw knowledge into a specified number of high-quality
    learning units. Each flashcard consists of a concise question or concept
    paired with a precise answer or explanation, optimized for active recall
    and spaced repetition.

    Args:
        information (str): The foundational text, technical data, or factual
            source used to extract definitions and facts.
        count (int, optional): The number of flashcards to generate.
            Defaults to 3.

    Returns:
        list[dict]: A collection of flashcard objects, each containing
            'question' and 'answer' keys.

    Notes:
        - The output is rendered to the user automatically via a dedicated UI
          component.
        - CRITICAL: To prevent redundancy, do not manually restate or
          summarize the returned flashcards in the final text response.
    """

    # 1️⃣ 构造 prompt
    prompt = (
        get_flashcard_prompt()
        .replace("{{information}}", information)
        .replace("{{count}}", str(count))
    )

    # 2️⃣ 获取 LLM 实例 (延迟加载)
    # 只有工具被真正调用时，才会去构建 LLM 实例
    llm_instance = get_llm()

    try:
        # 3. 关键：透传 config。这确保了：
        #    a) 计费 Callback 能拿到正确的 run_id
        #    b) LangSmith 里的追踪树是连贯的
        response = await llm_instance.ainvoke(prompt)
        content = response.content
    except Exception as e:
        return {"status": "failed", "message": f"LLM invocation error: {e}"}

    # 3️⃣ JSON 解析（更健壮的容错）
    try:
        generated_flashcards = json.loads(content)
    except JSONDecodeError:
        try:
            # 处理 LLM 可能返回的 Markdown 围栏
            clean_content = content.replace("```json", "").replace("```", "").strip()
            start = clean_content.find("[")
            end = clean_content.rfind("]") + 1
            generated_flashcards = json.loads(clean_content[start:end])
        except Exception:
            return {
                "status": "failed",
                "message": "Failed to parse JSON from LLM response.",
            }

    # 4️⃣ 结果校验
    if not isinstance(generated_flashcards, list):
        generated_flashcards = []

    # 5️⃣ 标准输出
    return {
        "flashcards": generated_flashcards[:5],
        "count": len(generated_flashcards[:5]),
        "status": "success",
    }


if __name__ == "__main__":
    test_input = """
    Redis 是一种基于内存的键值存储系统，常用于缓存、分布式锁和消息队列。
    分布式锁用于在分布式系统中控制多个节点对共享资源的访问，避免并发问题。
    """

    # result = flashcards_generate_tool.run(
    #    tool_input={"information": test_input, "count": 5}
    # )
    result = flashcards_generate_tool.run(test_input)
    print("=== RESULT ===")
    print(result)

    # ✅ 基本结构校验
    assert isinstance(result, dict), "返回结果必须是 dict"
    assert "flashcards" in result, "缺少 flashcards 字段"

    flashcards = result["flashcards"]

    assert isinstance(flashcards, list), "flashcards 必须是 list"
    assert 0 < len(flashcards) <= 5, "闪卡数量必须在 1-5 之间"

    # ✅ 每个卡片结构校验
    for card in flashcards:
        assert "question" in card, "缺少 question"
        assert "answer" in card, "缺少 answer"
        assert isinstance(card["question"], str)
        assert isinstance(card["answer"], str)

    print("✅ Test passed!")
