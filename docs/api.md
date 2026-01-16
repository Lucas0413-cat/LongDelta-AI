# API 接口文档

## 概述

LongDelta-AI 提供 RESTful API 接口，基于 FastAPI 构建，自动生成 OpenAPI/Swagger 文档。

访问地址: http://localhost:8000/docs

## 端点列表

### GET /health

健康检查端点，用于验证服务状态。

**响应示例:**
```json
{
  "status": "ok",
  "dataset_ok": true,
  "llm_ok": true,
  "dataset_path": "data/processed/yz_delta_mock_5y.parquet",
  "model": "deepseek-chat"
}
```

### POST /chat

同步对话端点，接收问题并返回分析结果。

**请求参数:**
```json
{
  "question": "分析2023年安徽GDP",
  "include_trace": false
}
```

**响应示例:**
```json
{
  "answer": "{\"region\": \"安徽\", \"indicator\": \"GDP\", ...}",
  "trace": []
}
```

### POST /chat/stream

流式对话端点，使用 Server-Sent Events (SSE) 实时输出分析进度和结果。

**请求参数:**
```json
{
  "question": "对比江浙沪三产结构"
}
```

**事件类型:**

| 事件类型 | 说明 | 数据格式 |
|----------|------|----------|
| `start` | 开始处理 | `{"status": "started"}` |
| `thinking` | LLM 思考中 | `{"message": "LLM 正在分析..."}` |
| `tool_call` | 工具调用 | `{"tool": "parse_query", "status": "started"}` |
| `tool_result` | 工具返回 | `{"tool": "parse_query", "status": "completed"}` |
| `message` | 消息内容 | `{"chunk": "...", "type": "token\|final"}` |
| `done` | 处理完成 | `{"status": "completed"}` |
| `error` | 错误信息 | `{"error": "错误描述"}` |

**响应示例:**
```
event: thinking
data: {"message": "LLM 正在分析..."}

event: tool_call
data: {"tool": "parse_query", "status": "started"}

event: tool_result
data: {"tool": "parse_query", "status": "completed"}

event: message
data: {"chunk": "{\"region\": \"安徽\"...", "type": "final"}

event: done
data: {"status": "completed"}
```

## 错误处理

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 500 | 服务器内部错误 |

**错误响应:**
```json
{
  "error": "请求包含敏感内容",
  "detail": "您的请求包含不当内容，请重新输入"
}
```

## 中间件

### 请求日志

所有请求都会被记录到控制台：
```
[2024-01-15 10:30:00] POST /chat | IP: 127.0.0.1
[2024-01-15 10:30:01] POST /chat | Status: 200 | Time: 0.523s
```

### 敏感词过滤

请求体中的敏感词会被检测并拒绝：
- 暴力、毒品、赌博、诈骗、色情、恐怖
- 分裂、颠覆、抗议、示威、自杀

### 响应时间

响应头包含处理时间：
```
X-Process-Time: 0.523
```
