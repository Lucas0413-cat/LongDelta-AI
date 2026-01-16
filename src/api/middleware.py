"""API Middleware for LongDelta-AI.

Provides:
- Request logging
- Sensitive word filtering
- Response timing
"""
from __future__ import annotations

import re
import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

# 敏感词列表（示例，可扩展）
SENSITIVE_WORDS = [
    "暴力", "毒品", "赌博", "诈骗", "色情", "恐怖",
    "分裂", "颠覆", "抗议", "示威", "自杀"
]

# 编译正则表达式
SENSITIVE_PATTERN = re.compile(
    r"|".join(re.escape(word) for word in SENSITIVE_WORDS),
    re.IGNORECASE
)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Request logging middleware."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        # 记录请求开始时间
        start_time = time.time()

        # 获取请求信息
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        # 记录请求体（如果有）
        body = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                body_str = body.decode("utf-8")
                # 限制日志长度
                if len(body_str) > 1000:
                    body_str = body_str[:1000] + "..."
            except Exception:
                body_str = "<解析失败>"

        # 打印请求日志
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {method} {path} | IP: {client_ip}")

        # 处理请求
        response = await call_next(request)

        # 计算响应时间
        process_time = time.time() - start_time

        # 记录响应状态
        status_code = response.status_code

        # 打印响应日志
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {method} {path} | "
              f"Status: {status_code} | Time: {process_time:.3f}s")

        return response


class SensitiveWordFilterMiddleware(BaseHTTPMiddleware):
    """Sensitive word filtering middleware for request body."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        # 只处理特定端点的 POST 请求
        if request.method in ["POST", "PUT", "PATCH"] and "/chat" in request.url.path:
            try:
                body = await request.body()
                body_str = body.decode("utf-8")

                # 检查敏感词
                match = SENSITIVE_PATTERN.search(body_str)
                if match:
                    print(f"[安全] 检测到敏感词 '{match.group()}'，拒绝请求")
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "请求包含敏感内容",
                            "detail": "您的请求包含不当内容，请重新输入"
                        }
                    )

                # 创建新的请求体（过滤后的）
                request._body = body

            except Exception as e:
                print(f"[错误] 敏感词过滤失败: {e}")

        return await call_next(request)


class ResponseTimeMiddleware(BaseHTTPMiddleware):
    """Response time header middleware."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        # 添加响应时间头
        response.headers["X-Process-Time"] = f"{process_time:.3f}"

        return response


def setup_middleware(app):
    """Setup all middleware for the FastAPI app."""
    # 添加中间件（顺序重要：先过滤，再日志）
    app.add_middleware(SensitiveWordFilterMiddleware)
    app.add_middleware(ResponseTimeMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
