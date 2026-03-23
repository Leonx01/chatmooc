import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Union

from langchain.tools import tool
from pydantic import BaseModel, Field, field_validator
from langchain_core.runnables import RunnableConfig

# 导入工厂函数，而不是实例
from app.agents.llm_factory import get_llm

# ===== 路径配置 =====
BASE_DIR = Path(__file__).resolve().parent.parent
PROMPT_PATH = BASE_DIR / "prompts" / "exercise.md"

def get_exercise_prompt() -> str:
    """懒加载 Prompt 内容"""
    global _EXERCISE_PROMPT
    if '_EXERCISE_PROMPT' not in globals():
        with open(PROMPT_PATH, "r", encoding="utf-8") as f:
            _EXERCISE_PROMPT = f.read()
    return _EXERCISE_PROMPT

class ExerciseInput(BaseModel):
    information: str = Field(..., description="学习内容")
    count: int = Field(default=3, description="选择题数量（3-5）")

    @field_validator("count")
    @classmethod
    def validate_count(cls, v):
        return max(3, min(5, v))

# ===== Tool =====
@tool("exercise_generate_tool", args_schema=ExerciseInput)
async def exercise_generate_tool(
    information: str,
    count: int = 3,
) -> Union[str, dict]:
    """
    Learning Exercise Generation Tool
    Purpose:
        Transforms raw technical knowledge (information) into structured, interactive
        practice questions. This tool acts as a "knowledge-distiller," extracting
        core principles and edge cases to create Multiple-Choice Questions (MCQs)
        that evaluate a learner's ability to apply raw information to specific scenarios.
    Parameters:
        information (str): The raw, foundational knowledge source (e.g., documentation,
                           technical specs, or raw text). This is the "Ground Truth"
                           from which questions, distractors, and logical explanations
                           are derived.
        count (int, optional): The number of unique practice questions to generate.
                               Defaults to 3.
    """

    # 1️⃣ 构造 prompt
    prompt = (
        get_exercise_prompt()
        .replace("{{information}}", information)
        .replace("{{count}}", str(count))
    )

    # 2️⃣ 获取 LLM 实例 (懒加载)
    llm_instance = get_llm()

    try:
        # 使用 ainvoke 并在调用时透传 config
        response = await llm_instance.ainvoke(prompt)
        content = response.content
    except Exception as e:
        return {"status": "failed", "message": f"LLM invocation error: {e}"}

    # 3️⃣ JSON 解析
    try:
        generated_exercise = json.loads(content)
    except JSONDecodeError:
        try:
            # 容错：处理包含 Markdown 代码块的情况
            clean_content = content.replace("```json", "").replace("```", "").strip()
            start = clean_content.find("[")
            end = clean_content.rfind("]") + 1
            generated_exercise = json.loads(clean_content[start:end])
        except Exception as e:
            return {"status": "failed", "message": f"JSON Parse error: {e}. Content: {content[:100]}"}

    # 4️⃣ 校验与返回
    if not isinstance(generated_exercise, list):
        generated_exercise = []

    return {
        "type": "exercise",
        "exercise": generated_exercise[:5],
        "count": len(generated_exercise[:5]),
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
    result = exercise_generate_tool.run(test_input)
    print("=== RESULT ===")
    print(result)

    print("✅ Test passed!")
