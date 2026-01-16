from __future__ import annotations

import json

from langchain_core.messages import HumanMessage
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from src.graph.state import AgentState
from src.tools.definitions import (
    calculate_growth_rate,
    get_multi_region_data,
    get_regional_data,
)
from src.tools.parse import parse_query
from src.utils.llm import init_llm

# ==================== 短板分析报告模型 ====================

class ShortBoardAnalysis(BaseModel):
    """短板分析子项"""
    weakness: str = Field(..., description="识别出的短板")
    severity: str = Field(..., description="严重程度: 轻微/中等/严重")
    suggestion: str = Field(..., description="改进建议")


class EconomicReport(BaseModel):
    """结构化经济分析报告（包含短板分析）- 单地区版"""
    region: str = Field(..., description="地区名称")
    indicator: str = Field(..., description="经济指标")
    year_current: int = Field(..., description="本期年份")
    year_previous: int = Field(..., description="对比年份")
    value_current: float = Field(..., description="本期数值")
    value_previous: float = Field(..., description="对比期数值")
    unit: str = Field(..., description="数值单位")
    source: str = Field(..., description="数据来源")
    growth_rate_percent: str = Field(..., description="增长率（百分比）")
    growth_trend: str = Field(..., description="增长趋势")
    short_board_analysis: list[ShortBoardAnalysis] = Field(default_factory=list)
    conclusion: str = Field(..., description="综合分析结论")


class MultiRegionReport(BaseModel):
    """多地区对比报告"""
    regions: list[str] = Field(..., description="地区列表")
    indicator: str = Field(..., description="经济指标")
    year: int = Field(..., description="对比年份")
    data_summary: str = Field(..., description="数据汇总描述")
    comparison_analysis: str = Field(..., description="对比分析")
    ranking: list[dict] = Field(default_factory=list, description="排名")
    conclusion: str = Field(..., description="综合结论")


# ==================== Prompt 模板 ====================

REPORT_SYSTEM_PROMPT = """你是长三角经济分析专家，擅长通过数据对比精准识别地区经济发展的短板，并提供针对性的改进建议。

## 分析框架

### 1. 数据概览
- 客观、准确地呈现本期与对比期数据
- 突出关键指标数值和变化

### 2. 增长趋势分析
- 计算并分析增长率
- 判断发展趋势：快速增长/稳步增长/基本持平/明显下滑
- 与全国平均增速对比（如有数据）

### 3. 短板识别（重点）
请从以下维度逐一分析：

**增长动能维度**
- 增长率是否低于全国平均水平？
- 增速较上期变化如何？
- 新兴产业贡献度如何？

**产业结构维度**
- 三产结构是否合理？
- 高附加值产业占比？
- 传统产业转型升级进度？

**区域协调维度**
- 省内区域发展是否均衡？
- 中心城市与周边差距？
- 城乡发展差距？

**创新驱动维度**
- 研发投入强度？
- 高技术产业发展？
- 人才吸引力？

### 4. 改进建议（必须具体可操作）
针对每个短板，给出：
- 具体政策措施建议
- 责任主体建议
- 预期效果

## 分析原则
1. **数据为王**：严格基于数据，不得更改任何数值
2. **量化分析**：用数据说话，避免空泛结论
3. **精准诊断**：短板要具体到领域和指标
4. **可操作性**：建议要落地，可执行"""


MULTI_REGION_PROMPT = """你是长三角经济分析专家，擅长区域经济对比分析。

## 任务
对比分析多个地区在同一指标上的表现，生成结构化报告。

## 分析维度

### 1. 数据汇总
- 各地区数据概览
- 绝对值与相对值

### 2. 对比分析
- 找出领先项和落后项
- 分析差距原因
- 识别各自优势

### 3. 排名分析
- 按指标值降序排列
- 标注差距百分比

### 4. 综合结论
- 区域发展格局总结
- 协同发展建议

## 输出要求
1. 严格按照给定数据
2. 排名要清晰（含具体数值）
3. 结论要有洞察和预判"""


def build_graph():
    llm = init_llm()

    # 两种输出模式
    single_llm = llm.with_structured_output(EconomicReport)
    multi_llm = llm.with_structured_output(MultiRegionReport)

    graph = StateGraph(AgentState)

    # 1) parse：确定 region(s) / 年份 / 指标
    def parse_node(state: AgentState):
        question = state["messages"][-1].content
        parsed = parse_query.invoke({"question": question})
        return {"context": {"parsed": parsed.model_dump()}}

    # 2a) 单地区：fetch current
    def fetch_current_node(state: AgentState):
        p = state["context"]["parsed"]
        r = get_regional_data.invoke({
            "region": p["regions"][0],
            "year": p["year_current"],
            "indicators": [p["indicator"]]
        })
        state.setdefault("context", {})
        state["context"]["current"] = r.model_dump()
        return {"context": state["context"]}

    # 2b) 单地区：fetch previous
    def fetch_prev_node(state: AgentState):
        p = state["context"]["parsed"]
        r = get_regional_data.invoke({
            "region": p["regions"][0],
            "year": p["year_previous"],
            "indicators": [p["indicator"]]
        })
        state["context"]["previous"] = r.model_dump()
        return {"context": state["context"]}

    # 3a) 单地区：calc growth
    def calc_node(state: AgentState):
        cur = state["context"]["current"]["data"][0]
        prev = state["context"]["previous"]["data"][0]
        g = calculate_growth_rate.invoke({"current": cur["value"], "previous": prev["value"]})
        state["context"]["growth"] = g.model_dump()
        return {"context": state["context"]}

    # 2c) 多地区：fetch multi-region data
    def fetch_multi_node(state: AgentState):
        p = state["context"]["parsed"]
        r = get_multi_region_data.invoke({
            "regions": p["regions"],
            "year": p["year_current"],
            "indicators": [p["indicator"]]
        })
        state.setdefault("context", {})
        state["context"]["multi_data"] = r.model_dump()
        return {"context": state["context"]}

    # 4a) 单地区报告
    def report_single_node(state: AgentState):
        p = state["context"]["parsed"]
        cur = state["context"]["current"]["data"][0]
        prev = state["context"]["previous"]["data"][0]
        g = state["context"]["growth"]["growth_rate"]

        # 增长趋势判断
        if g > 0.05:
            growth_trend = "快速增长"
        elif g > 0:
            growth_trend = "稳步增长"
        elif g > -0.05:
            growth_trend = "基本持平"
        else:
            growth_trend = "明显下滑"

        user_prompt = f"""分析以下经济数据：

地区：{p['regions'][0]}
指标：{p['indicator']}
本期（{p['year_current']}）：{cur['value']} {cur.get('unit','')}
对比期（{p['year_previous']}）：{prev['value']} {prev.get('unit','')}
增长率：{g:.6f}，增长趋势：{growth_trend}

请生成包含短板分析的结构化报告。"""

        report = single_llm.invoke([
            HumanMessage(content=REPORT_SYSTEM_PROMPT),
            HumanMessage(content=user_prompt)
        ])

        report_data = report.model_dump()
        report_data.setdefault("short_board_analysis", [])

        return {"messages": [HumanMessage(content=json.dumps(report_data, indent=2, ensure_ascii=False))]}

    # 4b) 多地区报告
    def report_multi_node(state: AgentState):
        p = state["context"]["parsed"]
        data = state["context"]["multi_data"]
        data_list = data["data"]

        # 构建数据汇总
        data_summary_parts = []
        for item in data_list:
            data_summary_parts.append(
                f"{item['region']}: {item['value']} {item.get('unit','')}"
            )
        data_summary = "；".join(data_summary_parts)

        # 排名
        sorted_data = sorted(data_list, key=lambda x: x.get("value", 0), reverse=True)
        ranking = [
            {"rank": i+1, "region": d["region"], "value": d.get("value", 0)}
            for i, d in enumerate(sorted_data)
        ]

        user_prompt = f"""对比分析以下多地区数据：

地区列表：{', '.join(p['regions'])}
指标：{p['indicator']}
年份：{p['year_current']}
数据汇总：{data_summary}

请生成多地区对比分析报告，包括:
1. 数据汇总描述
2. 对比分析
3. 排名（按指标值降序）
4. 综合结论"""

        report = multi_llm.invoke([
            HumanMessage(content=MULTI_REGION_PROMPT),
            HumanMessage(content=user_prompt)
        ])

        report_data = report.model_dump()
        report_data["regions"] = p["regions"]
        report_data["indicator"] = p["indicator"]
        report_data["year"] = p["year_current"]
        report_data["ranking"] = ranking

        return {"messages": [HumanMessage(content=json.dumps(report_data, indent=2, ensure_ascii=False))]}

    # 条件边：判断单地区还是多地区
    def should_continue(state: AgentState) -> str:
        p = state["context"]["parsed"]
        if p.get("is_multi_region", False):
            return "fetch_multi"
        else:
            return "fetch_current"

    # 添加节点
    graph.add_node("parse", parse_node)
    graph.add_node("fetch_current", fetch_current_node)
    graph.add_node("fetch_prev", fetch_prev_node)
    graph.add_node("calc", calc_node)
    graph.add_node("fetch_multi", fetch_multi_node)
    graph.add_node("report_single", report_single_node)
    graph.add_node("report_multi", report_multi_node)

    # 设置流程
    graph.set_entry_point("parse")
    graph.add_conditional_edges("parse", should_continue)

    # 单地区流程
    graph.add_edge("fetch_current", "fetch_prev")
    graph.add_edge("fetch_prev", "calc")
    graph.add_edge("calc", "report_single")
    graph.add_edge("report_single", END)

    # 多地区流程
    graph.add_edge("fetch_multi", "report_multi")
    graph.add_edge("report_multi", END)

    return graph.compile()
