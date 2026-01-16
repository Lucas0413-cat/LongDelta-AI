from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.api.middleware import setup_middleware
from src.api.schemas import ChatRequest, ChatResponse, HealthResponse, ToolTraceItem
from src.graph.workflow import build_graph
from src.tools.implementation import DATA_PATH, load_dataset
from src.utils.config import get_settings
from src.utils.llm import init_llm

app = FastAPI(title="LongDelta-AI API", version="0.3.0")

# 初始化 middleware
setup_middleware(app)

_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
    return _graph


def _safe_json_loads(s: str) -> Any:
    try:
        return json.loads(s)
    except Exception:
        return s


def extract_tool_trace(messages: list[Any]) -> list[ToolTraceItem]:
    """
    从 LangChain messages 中提取工具调用轨迹：
    - AIMessage.tool_calls 里拿到 tool_name + args + id
    - ToolMessage 里拿到 tool_call_id 对应的结果
    """
    # 1) 收集所有 tool call（按 id 映射）
    calls_by_id: dict[str, dict[str, Any]] = {}

    for m in messages:
        if isinstance(m, AIMessage):
            tool_calls = getattr(m, "tool_calls", None) or getattr(m, "additional_kwargs", {}).get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    # 兼容不同结构
                    tc_id = tc.get("id") or tc.get("tool_call_id") or tc.get("name")
                    name = tc.get("name") or tc.get("function", {}).get("name")
                    args = tc.get("args") or tc.get("function", {}).get("arguments") or {}
                    # args 可能是字符串 JSON
                    if isinstance(args, str):
                        args = _safe_json_loads(args)
                    calls_by_id[str(tc_id)] = {"tool_name": name, "args": args, "result": None}

    # 2) 把 ToolMessage 的输出灌回去
    for m in messages:
        if isinstance(m, ToolMessage):
            tc_id = getattr(m, "tool_call_id", None)
            content = getattr(m, "content", None)
            if tc_id and str(tc_id) in calls_by_id:
                calls_by_id[str(tc_id)]["result"] = _safe_json_loads(content)

    # 3) 输出为列表（保持出现顺序：按 messages 扫描一遍更稳）
    trace: list[ToolTraceItem] = []
    seen = set()

    for m in messages:
        if isinstance(m, AIMessage):
            tool_calls = getattr(m, "tool_calls", None) or getattr(m, "additional_kwargs", {}).get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    tc_id = str(tc.get("id") or tc.get("tool_call_id") or tc.get("name"))
                    if tc_id in calls_by_id and tc_id not in seen:
                        seen.add(tc_id)
                        item = calls_by_id[tc_id]
                        trace.append(
                            ToolTraceItem(
                                tool_name=item["tool_name"],
                                args=item["args"],
                                result=item["result"],
                            )
                        )
    return trace


@app.get("/health", response_model=HealthResponse)
def health():
    s = get_settings()

    dataset_ok = False
    try:
        _ = load_dataset()
        dataset_ok = True
    except Exception:
        dataset_ok = False

    llm_ok = False
    try:
        _ = init_llm()
        llm_ok = True
    except Exception:
        llm_ok = False

    return HealthResponse(
        status="ok" if (dataset_ok and llm_ok) else "degraded",
        dataset_ok=dataset_ok,
        llm_ok=llm_ok,
        dataset_path=str(DATA_PATH),
        model=s.llm_model,
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    try:
        graph = get_graph()
        state = {"messages": [HumanMessage(content=req.question)]}
        out = graph.invoke(state)

        msgs = out["messages"]
        answer = msgs[-1].content

        if req.include_trace:
            trace = out.get("context", {}).get("trace", [])
            return ChatResponse(answer=answer, trace=trace)

        return ChatResponse(answer=answer)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    流式对话接口，使用 Server-Sent Events (SSE)

    事件类型:
    - start: 开始处理
    - thinking: Agent 思考中
    - tool_call: 工具调用
    - tool_result: 工具返回
    - message: LLM 输出的 token 或最终消息
    - done: 完成
    - error: 错误
    """
    async def generate() -> AsyncGenerator[str, None]:
        try:
            graph = get_graph()
            state = {"messages": [HumanMessage(content=req.question)]}

            # 发送开始事件
            yield f"event: start\ndata: {json.dumps({'status': 'started'})}\n\n"

            # 用于累积最终内容
            final_content = ""

            # 使用 astream_events 流式输出
            async for event in graph.astream_events(state, version="v1"):
                event_type = event["event"]

                if event_type == "on_chain_start":
                    if event["name"] == "LangGraph":
                        msg = "开始处理"
                        yield f"event: thinking\ndata: {json.dumps({'message': msg})}\n\n"

                elif event_type == "on_chat_model_start":
                    yield f"event: thinking\ndata: {json.dumps({'message': 'LLM 正在分析...'})}\n\n"

                elif event_type == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk", {})
                    content = getattr(chunk, "content", "") or ""
                    if content:
                        final_content += content
                        yield f"event: message\ndata: {json.dumps({'chunk': content, 'type': 'token'})}\n\n"

                elif event_type == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    data = json.dumps({"tool": tool_name, "status": "started"})
                    yield f"event: tool_call\ndata: {data}\n\n"

                elif event_type == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    data = json.dumps({"tool": tool_name, "status": "completed"})
                    yield f"event: tool_result\ndata: {data}\n\n"

                elif event_type == "on_chain_end":
                    if event["name"] == "LangGraph":
                        output = event.get("data", {}).get("output", {})
                        if "messages" in output:
                            messages = output["messages"]
                            if messages:
                                # 获取最后一条消息作为最终结果
                                last_msg = messages[-1]
                                msg_content = getattr(last_msg, "content", "") or ""
                                if msg_content and msg_content != final_content:
                                    # 如果累积的内容和最终消息不同，发送剩余部分
                                    remaining = msg_content[len(final_content):]
                                    if remaining:
                                        yield f"event: message\ndata: {json.dumps({'chunk': remaining, 'type': 'token'})}\n\n"

                                # 发送 final 事件，包含完整内容
                                yield f"event: message\ndata: {json.dumps({'chunk': msg_content, 'type': 'final'})}\n\n"

            # 发送完成事件
            yield f"event: done\ndata: {json.dumps({'status': 'completed'})}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
