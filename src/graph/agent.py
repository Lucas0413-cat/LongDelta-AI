from __future__ import annotations

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool

from src.utils.llm import init_llm

SYSTEM_PROMPT = """你是LongDelta-AI的经济分析师。
你必须优先调用工具获取真实数据，再进行对比分析。
输出要求：条理清晰、可复述关键数据、结论明确。"""


def create_agent(tools: list[BaseTool]) -> Runnable:
    llm = init_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            ("placeholder", "{messages}"),
        ]
    )
    return prompt | llm.bind_tools(tools)
