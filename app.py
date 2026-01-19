"""
LongDelta-AI Streamlit Frontend

Features:
- Streaming response from FastAPI backend
- Real-time message display with auto-scroll
- Interrupt handling for concurrent requests
- Chart rendering with None tolerance
- Formula detection and conversion
"""
from __future__ import annotations

import json
import os
import re
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
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")


def eval_formula(formula: str) -> str | None:
    """评估公式表达式，返回计算后的数值字符串

    支持格式:
    - math.round(x * 10000) / 100
    - math.round(x) / 100
    - round(x * 100) / 100
    - (a - b) / b * 100
    - x * 100
    """
    if not formula or not isinstance(formula, str):
        return None

    formula = formula.strip()

    # 0. 处理 math.round(x) / divisor 格式 (无乘法)
    # 如: math.round(3.2300) / 100 -> 3.23
    simple_round_pattern = r"math\.round\(([\d.]+)\)\s*/\s*([\d.]+)"
    match = re.search(simple_round_pattern, formula)
    if match:
        try:
            num = float(match.group(1))
            divisor = float(match.group(2))
            if divisor != 0:
                result = round(num) / divisor
                return f"{result:.2f}"
        except (ValueError, ZeroDivisionError):
            pass

    # 1. 处理更通用的 math.round(x * 1000) / 10 格式
    # 支持任意乘数和除数
    generic_round_pattern = r"math\.round\(([\d.]+)\s*\*\s*([\d.]+)\)\s*/\s*([\d.]+)"
    match = re.search(generic_round_pattern, formula)
    if match:
        try:
            num = float(match.group(1))
            multiplier = float(match.group(2))
            divisor = float(match.group(3))
            if divisor != 0:
                result = round(num * multiplier) / divisor
                return f"{result:.2f}"
        except (ValueError, ZeroDivisionError):
            pass

    # 2. 处理 math.round(...) / divisor 格式
    # 如: math.round(0.0323 * 10000) / 100 -> 3.23
    round_pattern = r"math\.round\(([\d.]+)\s*\*\s*(\d+)\)\s*/\s*(\d+)"
    match = re.search(round_pattern, formula)
    if match:
        try:
            num = float(match.group(1))
            multiplier = int(match.group(2))
            divisor = int(match.group(3))
            result = round(num * multiplier) / divisor
            return f"{result:.2f}"
        except (ValueError, ZeroDivisionError):
            pass

    # 3. 处理 round(x * 100) / 100 格式
    round_pattern2 = r"round\(([\d.]+)\s*\*\s*(\d+)\)\s*/\s*(\d+)"
    match = re.search(round_pattern2, formula)
    if match:
        try:
            num = float(match.group(1))
            multiplier = int(match.group(2))
            divisor = int(match.group(3))
            result = round(num * multiplier) / divisor
            return f"{result:.2f}"
        except (ValueError, ZeroDivisionError):
            pass

    # 4. 处理 (a - b) / b * 100 格式 (计算百分比变化)
    pct_pattern = r"\(([\d.]+)\s*-\s*([\d.]+)\)\s*/\s*([\d.]+)\s*\*\s*100"
    match = re.search(pct_pattern, formula)
    if match:
        try:
            a = float(match.group(1))
            b = float(match.group(2))
            if b != 0:
                result = ((a - b) / b) * 100
                return f"{result:.2f}"
        except (ValueError, ZeroDivisionError):
            pass

    # 5. 处理简单的 x * 100 格式
    simple_pattern = r"^([\d.]+)\s*\*\s*100$"
    match = re.match(simple_pattern, formula)
    if match:
        try:
            num = float(match.group(1))
            result = num * 100
            return f"{result:.2f}"
        except ValueError:
            pass

    return None


def clean_formulas_in_text(text: str) -> str:
    """清理文本中的公式，将其替换为计算后的数值"""
    if not text or not isinstance(text, str):
        return text

    # 递归替换所有公式格式
    def replace_formula(match):
        full_match = match.group(0)
        result = eval_formula(full_match)
        return result if result is not None else full_match

    # 匹配各种公式模式
    patterns = [
        r"math\.round\([\d.]+\)\s*/\s*[\d.]+",  # math.round(x)/... (无乘法)
        r"math\.round\([\d.]+\s*\*\s*[\d.]+\)\s*/\s*[\d.]+",  # math.round(...)/... (通用)
        r"round\([\d.]+\s*\*\s*\d+\)\s*/\s*\d+",        # round(...)/...
        r"\([\d.]+\s*-\s*[\d.]+\)\s*/\s*[\d.]+\s*\*\s*100",  # (a-b)/b*100
        r"[\d.]+\s*\*\s*100",  # x*100
    ]

    for pattern in patterns:
        text = re.sub(pattern, replace_formula, text)

    return text


def clean_report_data(data: dict) -> dict:
    """清理报告数据中的所有公式"""
    if not isinstance(data, dict):
        return data

    cleaned = {}
    for key, value in data.items():
        if isinstance(value, str):
            # 清理字符串中的公式
            cleaned[key] = clean_formulas_in_text(value)
        elif isinstance(value, dict):
            # 递归处理嵌套字典
            cleaned[key] = clean_report_data(value)
        elif isinstance(value, list):
            # 处理列表
            cleaned[key] = [
                clean_report_data(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            cleaned[key] = value

    return cleaned


def parse_growth_rate(value):
    """解析增长率，处理公式或数字格式，返回保留两位小数的百分数字符串"""
    if value is None:
        return ""

    # 如果已经是数字
    if isinstance(value, (int, float)):
        return f"{value:.2f}%"

    # 如果是字符串，先尝试清理公式
    if isinstance(value, str):
        # 尝试直接解析为数字
        try:
            num = float(value.strip())
            return f"{num:.2f}%"
        except ValueError:
            pass

        # 尝试清理公式
        cleaned = clean_formulas_in_text(value.strip())
        if cleaned != value:
            try:
                num = float(cleaned)
                return f"{num:.2f}%"
            except ValueError:
                pass

        return cleaned

    return str(value)


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

    # 先清理数据中的所有公式
    data = clean_report_data(data)

    # 数据概览
    st.markdown("### 📊 分析报告")

    col1, col2, col3 = st.columns(3)
    with col1:
        # 获取并解析增长率
        growth_rate_value = data.get('growth_rate_percent', {})
        if isinstance(growth_rate_value, dict):
            rate_value = growth_rate_value.get('value', 0)
        else:
            rate_value = growth_rate_value
        parsed_rate = parse_growth_rate(rate_value)

        st.metric(
            label=data.get("region", "") + " " + data.get("indicator", ""),
            value=f"{data.get('value_current', 0):,.2f}",
            delta=parsed_rate
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
    growth_rate_data = data.get("growth_rate_percent", {})

    if isinstance(growth_rate_data, dict):
        # LLM 返回 dict 格式: {"value": 3.23, "unit": "%", "description": "..."}
        rate_value = growth_rate_data.get('value', '')
        unit = growth_rate_data.get('unit', '')
        # 优先使用 description，如果没有则使用 value
        note = growth_rate_data.get('description', '') or growth_rate_data.get('note', '')
        parsed_rate = parse_growth_rate(rate_value)
        st.markdown(f"**增长率**: {parsed_rate} {unit} ({note})")
    elif isinstance(growth_rate_data, str):
        # 原始字符串格式
        parsed_rate = parse_growth_rate(growth_rate_data)
        st.markdown(f"**增长率**: {parsed_rate}")
    else:
        # 其他情况
        st.markdown(f"**增长率**: {str(growth_rate_data)}")

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

    # 先清理数据中的所有公式
    data = clean_report_data(data)

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


def scroll_to_top():
    """滚动到页面顶部（用户问题位置）"""
    st.components.v1.html(
        """
        <script>
        setTimeout(function() {
            const el = document.getElementById("question-top");
            if (el) el.scrollIntoView({behavior: "smooth", block: "start"});
        }, 300);
        </script>
        """,
        height=0
    )


def scroll_to_bottom():
    """滚动到页面底部（响应结果位置）"""
    st.components.v1.html(
        """
        <script>
        setTimeout(function() {
            const elements = document.querySelectorAll('[data-testid="stChatMessageContent"]');
            if (elements.length > 0) {
                elements[elements.length - 1].scrollIntoView({behavior: "smooth", block: "center"});
            }
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
    
    # 仅在没有消息时显示提示文字
    if not st.session_state.get("messages"):
        st.markdown("输入您的问题，获取智能分析报告")

    # Chat input
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 问题锚点 - 用于滚动到用户问题位置
    question_anchor = st.empty()
    question_anchor.markdown('<div id="question-top"></div>', unsafe_allow_html=True)

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

    # Question input
    question = st.chat_input("请输入您的问题...")

    if question:
        # 添加用户问题锚点标记
        question_anchor.markdown(f'<div id="question-{len(st.session_state.messages)}">{question}</div>', unsafe_allow_html=True)

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

                            elif event_type == "tool_result":
                                message_placeholder.success("✅ 工具执行完成")

                            elif event_type == "token":
                                chunk = event.get("chunk", "")
                                full_response += chunk
                                message_placeholder.markdown(full_response + "▌")

                            elif event_type == "final":
                                chunk = event.get("chunk", "")
                                full_response += chunk

                                # 检测报告类型
                                if is_multi_region_report(full_response):
                                    is_report = True
                                    message_placeholder.empty()
                                    render_multi_region_report(parse_report_data(full_response))
                                elif is_analysis_report(full_response):
                                    is_report = True
                                    message_placeholder.empty()
                                    render_analysis_report(parse_report_data(full_response))
                                else:
                                    message_placeholder.markdown(full_response)

                                chart_data = event.get("chart") if isinstance(event.get("chart"), dict) else None

                            elif event_type == "done":
                                if cancelled:
                                    break
                                if not is_report:
                                    message_placeholder.markdown(full_response)
                                if chart_data:
                                    render_chart(chart_data)
                                break

                            elif event_type == "error":
                                st.error(f"错误: {event.get('error', '未知错误')}")
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

        # 响应完成后显示"滚动到底部"按钮
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            if st.button("📜 滚动到底部查看响应", use_container_width=True, key=f"scroll_bottom_{new_request_id}"):
                scroll_to_bottom()


if __name__ == "__main__":
    main()
