from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., description="用户问题")
    include_trace: bool = Field(default=False, description="是否返回工具调用轨迹")


class ToolTraceItem(BaseModel):
    tool_name: str
    args: dict[str, Any]
    result: Any


class ChatResponse(BaseModel):
    answer: str = Field(..., description="Agent 输出的最终回答")
    trace: list[ToolTraceItem] | None = Field(default=None, description="工具调用轨迹（可选）")


class HealthResponse(BaseModel):
    status: str
    dataset_ok: bool
    llm_ok: bool
    dataset_path: str
    model: str
