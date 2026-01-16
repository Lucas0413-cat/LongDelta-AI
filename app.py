"""
LongDelta-AI Streamlit Frontend

Features:
- Streaming response from FastAPI backend
- Real-time message display with auto-scroll
- Interrupt handling for concurrent requests
- Chart rendering with None tolerance
"""
from __future__ import annotations

import json
import uuid

import requests
import streamlit as st

# Page config
st.set_page_config(
    page_title="LongDelta-AI 经济分析助手",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# API endpoint - 从环境变量读取
import os
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")


def render_chart(chart_data: dict | None):
    """Render Plotly chart with None tolerance."""
    if not chart_data:
        return

    try:
        import plotly.express as px

        # None check
        if not isinstance(chart_data, dict):
            st.warning("图表数据为空")
            return

        chart_type = chart_data.get("type")

        if chart_type == "bar":
            fig = px.bar(
                chart_data.get("data", []),
                x=chart_data.get("x", "x"),
                y=chart_data.get("y", "y"),
                title=chart_data.get("title", "")
            )
        elif chart_type == "pie":
            fig = px.pie(
                chart_data.get("data", []),
                names=chart_data.get("names", "names"),
                values=chart_data.get("values", "values"),
                title=chart_data.get("title", "")
            )
        elif chart_type == "line":
            fig = px.line(
                chart_data.get("data", []),
                x=chart_data.get("x", "x"),
                y=chart_data.get("y", "y"),
                title=chart_data.get("title", "")
            )
        else:
            st.warning(f"不支持的图表类型: {chart_type}")
            return

        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"图表渲染失败: {str(e)}")


def render_analysis_report(data: dict):
    """美化的单地区经济分析报告渲染"""
    if not isinstance(data, dict):
        return

    # 数据概览
    st.markdown("### 📊 分析报告")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            label=data.get("region", "") + " " + data.get("indicator", ""),
            value=f"{data.get('value_current', 0):,.2f}",
            delta=f"{data.get('growth_rate_percent', {}).get('value', 0)}%" if isinstance(data.get('growth_rate_percent'), dict) else str(data.get('growth_rate_percent', ''))
        )
    with col2:
        st.metric(
            label="上期数值",
            value=f"{data.get('value_previous', 0):,.2f}",
            delta=data.get("unit", "")
        )
    with col3:
        st.metric(
            label="增长趋势",
            value=data.get("growth_trend", ""),
            delta=str(data.get("year_current", "")) + " vs " + str(data.get("year_previous", ""))
        )

    st.markdown("---")

    # 综合结论
    st.markdown("#### 📝 综合结论")
    st.info(data.get("conclusion", ""))

    # 增长详情
    if isinstance(data.get("growth_rate_percent"), dict):
        gr = data["growth_rate_percent"]
        st.markdown(f"**增长率**: {gr.get('value', '')}{gr.get('unit', '')} ({gr.get('note', '')})")
    else:
        st.markdown(f"**增长率**: {data.get('growth_rate_percent', '')}")

    st.markdown("---")

    # 短板分析
    if data.get("short_board_analysis"):
        st.markdown("#### ⚠️ 短板分析与建议")

        for i, item in enumerate(data["short_board_analysis"], 1):
            severity_emoji = {"轻微": "🟢", "中等": "🟡", "较高": "🟠", "严重": "🔴"}
            emoji = severity_emoji.get(item.get("severity", ""), "⚪")

            with st.expander(f"{emoji} 短板 {i}: {item.get('weakness', '')[:50]}..."):
                st.markdown(f"**严重程度**: {item.get('severity', '')}")
                st.markdown(f"**短板描述**: {item.get('weakness', '')}")
                st.markdown(f"**改进建议**: {item.get('suggestion', '')}")

    # 原始数据（可折叠）
    with st.expander("📄 原始数据"):
        st.json(data)


def render_multi_region_report(data: dict):
    """美化的多地区对比报告渲染"""
    if not isinstance(data, dict):
        return

    st.markdown("### 📊 多地区对比分析")

    regions = data.get("regions", [])
    indicator = data.get("indicator", "")
    year = data.get("year", "")

    # 标题
    st.markdown(f"#### {indicator}对比 ({year}年)")
    st.markdown(f"**对比地区**: {', '.join(regions)}")

    st.markdown("---")

    # 数据汇总
    st.markdown("#### 📈 数据汇总")
    st.info(data.get("data_summary", ""))

    # 排名表格
    if data.get("ranking"):
        st.markdown("#### 🏆 排名")
        ranking_data = data["ranking"]
        import pandas as pd
        df_ranking = pd.DataFrame(ranking_data)
        st.table(df_ranking)

        # 绘制排名柱状图
        import plotly.express as px

        # 动态获取列名
        df_ranking = pd.DataFrame(ranking_data)
        x_col = 'region' if 'region' in df_ranking.columns else ('area' if 'area' in df_ranking.columns else df_ranking.columns[0])

        fig = px.bar(
            df_ranking,
            x=x_col,
            y="value",
            title=f"{indicator}对比 ({year})",
            labels={x_col: "地区", "value": indicator}
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # 对比分析
    st.markdown("#### 🔍 对比分析")
    st.markdown(data.get("comparison_analysis", ""))

    st.markdown("---")

    # 综合结论
    st.markdown("#### 📝 综合结论")
    st.success(data.get("conclusion", ""))

    # 原始数据（可折叠）
    with st.expander("📄 原始数据"):
        st.json(data)


def extract_json_from_content(content: str) -> str:
    """从内容中提取 JSON 字符串（处理 Markdown 代码块等）"""
    # 移除 markdown 代码块标记
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
    elif content.startswith("```"):
        content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

    # 找到 JSON 对象的开始和结束
    start = content.find('{"')
    if start == -1:
        start = content.find('{"')  # 重新查找
        if start == -1:
            return content.strip()

    # 简单的括号匹配来找到结束位置
    brace_count = 0
    in_string = False
    for i, char in enumerate(content[start:], start):
        if char == '\\"' and in_string:
            continue
        if char == '"' and not in_string:
            in_string = True
        elif char == '"' and in_string:
            in_string = False
        if char == '{' and not in_string:
            brace_count += 1
        elif char == '}' and not in_string:
            brace_count -= 1
            if brace_count == 0:
                return content[start:i+1]

    return content.strip()


def is_multi_region_report(content: str) -> bool:
    """检测内容是否为多地区对比报告 JSON"""
    # 尝试提取干净的 JSON
    json_content = extract_json_from_content(content)

    try:
        data = json.loads(json_content)
        return (
            isinstance(data, dict) and
            "regions" in data and
            isinstance(data["regions"], list) and
            len(data["regions"]) > 1 and
            "comparison_analysis" in data
        )
    except (json.JSONDecodeError, TypeError, KeyError):
        return False


def is_analysis_report(content: str) -> bool:
    """检测内容是否为单地区分析报告 JSON"""
    # 尝试提取干净的 JSON
    json_content = extract_json_from_content(content)

    try:
        data = json.loads(json_content)
        return (
            isinstance(data, dict) and
            "region" in data and
            "indicator" in data and
            "conclusion" in data
        )
    except (json.JSONDecodeError, TypeError):
        return False


def parse_report_data(content: str) -> dict:
    """解析报告 JSON 数据"""
    # 尝试提取干净的 JSON
    json_content = extract_json_from_content(content)

    try:
        return json.loads(json_content)
    except json.JSONDecodeError:
        return {}


def scroll_to_bottom():
    st.components.v1.html(
        """
        <script>
        setTimeout(function() {
            const el = document.getElementById("chat-bottom");
            if (el) el.scrollIntoView({behavior: "auto", block: "end", inline: "nearest"});
        }, 100);
        </script>
        """,
        height=0
    )


def init_session_state():
    """Initialize session state for interrupt handling."""
    if "request_id" not in st.session_state:
        st.session_state.request_id = None
    if "processing" not in st.session_state:
        st.session_state.processing = False
    if "pending_clear" not in st.session_state:
        st.session_state.pending_clear = False


def main():
    init_session_state()

    # Sidebar
    with st.sidebar:
        st.title("📊 LongDelta-AI")
        st.markdown("### 经济数据分析助手")
        st.markdown("---")
        st.markdown("**示例问题:**")
        examples = [
            "分析2023年安徽GDP",
            "对比江浙沪三产结构",
            "江苏2023年CPI对比2022年",
            "上海近5年GDP变化趋势"
        ]
        for ex in examples:
            if st.button(ex, key=f"ex_{ex}"):
                st.session_state.question = ex

        st.markdown("---")
        st.markdown("**状态:**")
        if st.button("检查后端连接"):
            try:
                resp = requests.get(f"{API_BASE}/health", timeout=5)
                if resp.status_code == 200:
                    st.success("后端服务正常")
                else:
                    st.warning("后端服务异常")
            except Exception:
                st.error("无法连接后端")

    # Main content
    st.title("🏢 长三角经济分析助手")
    st.markdown("输入您的问题，获取智能分析报告")

    # Chat input
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Auto-scroll to bottom on new message
    if st.session_state.processing:
        scroll_to_bottom()

    # Display chat history
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if is_multi_region_report(msg["content"]):
                render_multi_region_report(parse_report_data(msg["content"]))
            elif is_analysis_report(msg["content"]):
                render_analysis_report(parse_report_data(msg["content"]))
            else:
                st.markdown(msg["content"])
            if msg.get("chart"):
                render_chart(msg["chart"])

    bottom_anchor = st.empty()
    bottom_anchor.markdown('<div id="chat-bottom"></div>', unsafe_allow_html=True)

    # Question input
    question = st.chat_input("请输入您的问题...")

    if question:
        # Interrupt: cancel previous request by generating new request_id
        new_request_id = str(uuid.uuid4())
        st.session_state.request_id = new_request_id
        st.session_state.processing = True

        # Clear pending state
        st.session_state.pending_clear = True

        # Add user message
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        # Get streaming response
        with st.chat_message("assistant"):
            message_placeholder = st.empty()
            full_response = ""
            chart_data = None
            is_report = False
            cancelled = False
            try:
                response = requests.post(
                    f"{API_BASE}/chat/stream",
                    json={"question": question},
                    stream=True,
                    timeout=60
                )
                response.raise_for_status()

                for line in response.iter_lines():
                    if line:
                        # Interrupt check: if request_id changed, stop processing
                        if st.session_state.request_id != new_request_id:
                            cancelled = True
                            # 1) 清空当前 assistant 这条消息的临时渲染
                            message_placeholder.warning("⛔ 已中断上一轮输出，开始处理新问题…")
                            # 2) 关闭连接，防止旧流继续占用
                            try:
                                response.close()
                            except Exception:
                                pass
                            # 3) 标记取消，阻止后续渲染/保存
                            break

                        line_str = line.decode("utf-8")
                        if line_str.startswith("data: "):
                            try:
                                event = json.loads(line_str[6:])
                            except json.JSONDecodeError:
                                continue

                            event_type = event.get("type", event.get("event", ""))

                            if event_type == "thinking" or event_type == "tool_call":
                                msg_text = event.get("message", event.get("tool", ""))
                                message_placeholder.info(f"🤔 {msg_text}")
                                scroll_to_bottom()

                            elif event_type == "tool_result":
                                message_placeholder.success("✅ 工具执行完成")
                                scroll_to_bottom()

                            elif event_type == "token":
                                chunk = event.get("chunk", "")
                                full_response += chunk
                                message_placeholder.markdown(full_response + "▌")
                                scroll_to_bottom()

                            elif event_type == "final":
                                chunk = event.get("chunk", "")
                                full_response += chunk

                                # 检测报告类型
                                if is_multi_region_report(full_response):
                                    is_report = True
                                    message_placeholder.empty()
                                    render_multi_region_report(parse_report_data(full_response))
                                    scroll_to_bottom()
                                elif is_analysis_report(full_response):
                                    is_report = True
                                    message_placeholder.empty()
                                    render_analysis_report(parse_report_data(full_response))
                                    scroll_to_bottom()
                                else:
                                    message_placeholder.markdown(full_response)
                                    scroll_to_bottom()

                                chart_data = event.get("chart") if isinstance(event.get("chart"), dict) else None
                                scroll_to_bottom()

                            elif event_type == "done":
                                if cancelled:
                                    break
                                if not is_report:
                                    message_placeholder.markdown(full_response)
                                    scroll_to_bottom()
                                if chart_data:
                                    render_chart(chart_data)
                                    scroll_to_bottom()
                                break

                            elif event_type == "error":
                                st.error(f"错误: {event.get('error', '未知错误')}")
                                scroll_to_bottom()
                                break

            except requests.exceptions.ConnectionError:
                st.error("无法连接到后端服务，请确保 FastAPI 服务正在运行")
            except Exception as e:
                st.error(f"请求错误: {str(e)}")

            # Save assistant response (only if not interrupted)
            if (not cancelled) and st.session_state.request_id == new_request_id:
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full_response,
                    "chart": chart_data
                })

        # Reset processing flag
        st.session_state.processing = False

        # Auto-scroll to bottom after response
        scroll_to_bottom()


if __name__ == "__main__":
    main()
