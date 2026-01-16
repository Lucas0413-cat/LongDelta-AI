from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.tools.implementation import load_dataset


class ParsedQuery(BaseModel):
    regions: list[str] = Field(default_factory=list, description="地区列表，如 [安徽, 江苏, 上海]")
    year_current: int = Field(..., description="本期年份，如 2023")
    year_previous: int = Field(..., description="对比年份，如 2022")
    indicator: str = Field(default="GDP", description="指标，如 GDP/CPI")
    is_multi_region: bool = Field(default=False, description="是否为多地区对比分析")


def normalize_region_name(name: str) -> str:
    """标准化地区名称，去除省/市后缀"""
    return name.rstrip("省市")


def get_region_variants(name: str) -> set[str]:
    """生成地区名称变体"""
    s = {name}
    if name.endswith(("省", "市")):
        s.add(name[:-1])
    else:
        s.add(name + "省")
        s.add(name + "市")
    return s


@tool
def parse_query(question: str) -> ParsedQuery:
    """
    Parse user question into structured query parameters.

    This tool extracts region(s), years, and indicator from natural language questions.
    Supports both single-region and multi-region comparison queries.

    Args:
        question: User's question in natural language
            (e.g., "安徽2023年GDP对比2022年", "对比江浙沪三产结构")

    Returns:
        ParsedQuery: Structured query with regions, years, indicator, and is_multi_region flag

    Raises:
        ValueError: If region(s) cannot be identified from the question
    """
    indicator = "GDP"
    year_current = 2023
    year_previous = 2022
    found_regions: list[str] = []

    q = str(question).strip()
    q_norm = "".join(q.split())  # 去空白（包含全角空格情况）

    # ---- indicator ----
    if "CPI" in q_norm.upper() or "物价" in q_norm:
        indicator = "CPI"
    if "GDP" in q_norm.upper() or "生产总值" in q_norm:
        indicator = "GDP"
    # 检测三产相关
    if "三产" in q_norm or "产业结构" in q_norm or "三次产业" in q_norm:
        indicator = "三产结构"

    # ---- years ----
    import re
    years = re.findall(r"(19\d{2}|20\d{2})", q_norm)
    years = [int(y) for y in years]
    if len(years) >= 2:
        year_current, year_previous = years[0], years[1]
    elif len(years) == 1:
        year_current = years[0]
        year_previous = years[0] - 1

    # ---- regions from dataset ----
    df = load_dataset()
    candidates = sorted({str(x) for x in df["region"].dropna().unique()}, key=len, reverse=True)

    # 检测是否为多地区对比（包含"对比"、"比较"、"三省"、"江浙沪"等关键词）
    is_multi = (
        "对比" in q_norm or
        "比较" in q_norm or
        "江浙沪" in q_norm or
        "三省" in q_norm or
        "长三角" in q_norm
    )

    if is_multi:
        # 多地区模式：查找所有匹配的地区
        for cand in candidates:
            for v in get_region_variants(cand):
                if v and v in q_norm:
                    region_name = normalize_region_name(cand)
                    if region_name not in found_regions:
                        found_regions.append(region_name)
    else:
        # 单地区模式：只找第一个匹配
        for cand in candidates:
            for v in get_region_variants(cand):
                if v and v in q_norm:
                    region_name = normalize_region_name(cand)
                    found_regions = [region_name]
                    break
            if found_regions:
                break

    # 兜底：抓 "xx省/xx市"
    if not found_regions:
        matches = re.findall(r"([\u4e00-\u9fff]{2,6})(省|市)", q_norm)
        for match in matches:
            region_name = match[0]
            if region_name not in found_regions:
                found_regions.append(region_name)

    # 江浙沪特殊处理
    if "江浙沪" in q_norm:
        found_regions = ["江苏", "浙江", "上海"]

    if not found_regions:
        raise ValueError("无法从问题中识别地区（region）。请在问题中包含如：安徽/上海/浙江/江苏等。")

    return ParsedQuery(
        regions=found_regions,
        year_current=year_current,
        year_previous=year_previous,
        indicator=indicator,
        is_multi_region=len(found_regions) > 1,
    )
