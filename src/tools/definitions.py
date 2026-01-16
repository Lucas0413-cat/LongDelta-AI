from __future__ import annotations

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.tools.implementation import growth_rate, query_multi_regional_data, query_regional_data


class RegionalDataPoint(BaseModel):
    region: str
    year: int
    indicator: str
    value: float
    unit: str | None = None
    source: str | None = None


class RegionalDataResponse(BaseModel):
    data: list[RegionalDataPoint] = Field(default_factory=list)


@tool
def get_regional_data(region: str, year: int, indicators: list[str]) -> RegionalDataResponse:
    """
    获取某地区某年份的宏观指标数据（结构化返回，便于前端/小程序使用）。

    Args:
        region: 地区名称（如：上海、江苏、浙江、安徽）
        year: 年份（如：2023）
        indicators: 指标列表（如：["GDP", "CPI"]）

    Returns:
        dict: {"data": [{"region","year","indicator","value","unit","source"}, ...]}
    """
    rows = query_regional_data(region=region, year=year, indicators=indicators)

    # rows 里如果没有 unit/source 也没关系，Pydantic 会用 None
    resp = RegionalDataResponse(data=[RegionalDataPoint(**r) for r in rows])
    return resp


class GrowthRateResponse(BaseModel):
    growth_rate: float = Field(..., description="增长率（如 0.05 表示 5%）")


@tool
def calculate_growth_rate(current: float, previous: float) -> GrowthRateResponse:
    """
    计算增长率。

    Args:
        current: 本期值
        previous: 上期值

    Returns:
        dict: {"growth_rate": 0.0323}
    """
    resp = GrowthRateResponse(growth_rate=growth_rate(current, previous))
    return resp


class MultiRegionDataResponse(BaseModel):
    """多地区数据对比响应"""
    data: list[RegionalDataPoint] = Field(default_factory=list)
    regions: list[str] = Field(default_factory=list)
    year: int
    indicator: str


@tool
def get_multi_region_data(regions: list[str], year: int, indicators: list[str]) -> MultiRegionDataResponse:
    """
    获取多个地区某年份的对比数据，用于区域对比分析。

    Args:
        regions: 地区名称列表（如：["江苏", "浙江", "上海"]）
        year: 年份（如：2023）
        indicators: 指标列表（如：["GDP", "三产占比"]）

    Returns:
        MultiRegionDataResponse: 包含多地区数据列表
    """
    rows = query_multi_regional_data(regions=regions, year=year, indicators=indicators)
    resp = MultiRegionDataResponse(
        data=[RegionalDataPoint(**r) for r in rows],
        regions=regions,
        year=year,
        indicator=indicators[0] if indicators else ""
    )
    return resp
