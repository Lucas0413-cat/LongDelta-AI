#!/usr/bin/env python
"""
测试后端流式输出
用法: python test_stream.py "分析2023年安徽GDP"
"""
import json
import sys

import requests

API_BASE = "http://localhost:8000"


def test_chat_stream(question: str):
    """测试流式对话接口"""
    print("=" * 60)
    print(f"测试问题: {question}")
    print("=" * 60)

    try:
        response = requests.post(
            f"{API_BASE}/chat/stream",
            json={"question": question},
            stream=True,
            timeout=120
        )
        response.raise_for_status()

        token_count = 0
        total_chars = 0
        final_content = ""
        all_events = []

        print("\n--- 流式输出开始 ---\n")

        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                all_events.append(line_str)
                print(f"[原始] {line_str[:100]}...")

                if line_str.startswith("data: "):
                    try:
                        event = json.loads(line_str[6:])
                        event_type = event.get("type", event.get("event", ""))

                        if event_type == "start":
                            print(f"[开始] {event}")

                        elif event_type == "thinking":
                            print(f"[思考] {event.get('message', '')}")

                        elif event_type == "tool_call":
                            print(f"[工具调用] {event.get('tool', '')}")

                        elif event_type == "tool_result":
                            print(f"[工具完成] {event.get('tool', '')}")

                        elif event_type == "token":
                            chunk = event.get("chunk", "")
                            if chunk:
                                token_count += 1
                                total_chars += len(chunk)
                                print(chunk, end="", flush=True)
                                final_content += chunk

                        elif event_type == "final":
                            chunk = event.get("chunk", "")
                            if chunk:
                                print("\n--- 最终消息 (type=final) ---")
                                print(chunk[:500] + "..." if len(chunk) > 500 else chunk)
                                final_content = chunk

                        elif event_type == "done":
                            print("\n--- 流式输出完成 ---")

                        elif event_type == "error":
                            print(f"\n[错误] {event.get('error', '未知错误')}")

                    except json.JSONDecodeError as e:
                        print(f"[JSON解析错误] {e}")

        print("\n" + "=" * 60)
        print("统计:")
        print(f"  - 总事件数: {len(all_events)}")
        print(f"  - Token 数量: {token_count}")
        print(f"  - 总字符数: {total_chars}")
        print(f"  - 最终内容长度: {len(final_content)} 字符")
        if final_content:
            print(f"  - 最终内容行数: {final_content.count(chr(10)) + 1} 行")
        print("=" * 60)

        # 验证内容完整性
        if final_content:
            print("\n[OK] 收到最终内容")
            if len(final_content) > 500:
                print("[OK] 内容长度超过 500 字符")
            if final_content.count(chr(10)) > 10:
                print("[OK] 内容行数超过 10 行")
        else:
            print("\n[FAIL] 未收到最终内容")
            print("调试: 检查后端日志看是否有错误")

    except requests.exceptions.ConnectionError:
        print(f"[FAIL] 无法连接到后端服务: {API_BASE}")
        print("请确保后端正在运行: uv run uvicorn src.api.server:app --reload")
    except Exception as e:
        print(f"[FAIL] 请求错误: {e}")


def test_health():
    """测试健康检查"""
    print("\n--- 健康检查 ---")
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=5)
        data = resp.json()
        print(f"状态: {data.get('status')}")
        print(f"数据集: {data.get('dataset_ok')}")
        print(f"LLM: {data.get('llm_ok')}")
        print(f"模型: {data.get('model')}")
    except Exception as e:
        print(f"[FAIL] 健康检查失败: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python test_stream.py <问题>")
        print("示例: python test_stream.py \"分析2023年安徽GDP\"")
        sys.exit(1)

    question = sys.argv[1]

    test_health()
    test_chat_stream(question)
