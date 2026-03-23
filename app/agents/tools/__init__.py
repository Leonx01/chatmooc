from typing import List

from langchain_core.tools import BaseTool

from .exercise_tool import exercise_generate_tool
from .fetch_info_tool import fetch_info_tool
from .flashcards_tool import flashcards_generate_tool
from .memo_tool import memo_tool

TOOLS: List[BaseTool] = [
    flashcards_generate_tool,
    fetch_info_tool,
    exercise_generate_tool,
    memo_tool,
]
