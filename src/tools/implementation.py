from __future__ import annotations

from pathlib import Path

import pandas as pd

DATA_PATH = Path("data/processed/yz_delta_mock_5y.parquet")


def load_dataset() -> pd.DataFrame:
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found: {DATA_PATH.resolve()}")
    df = pd.read_parquet(DATA_PATH)
    return normalize_df(df)


def query_regional_data(region: str, year: int, indicators: list[str]) -> list[dict]:
    df = load_dataset()
    out = df[(df["region"] == region) & (df["year"] == year) & (df["indicator"].isin(indicators))]
    return out.to_dict(orient="records")


def query_multi_regional_data(regions: list[str], year: int, indicators: list[str]) -> list[dict]:
    """查询多个地区的数据用于对比分析"""
    df = load_dataset()
    out = df[(df["region"].isin(regions)) & (df["year"] == year) & (df["indicator"].isin(indicators))]
    return out.to_dict(orient="records")


def growth_rate(current: float, previous: float) -> float:
    if previous == 0:
        raise ValueError("previous value is 0; cannot compute growth rate")
    return (current - previous) / previous

def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    统一成：region/year/indicator/value/unit/source 的长表。
    你的 yz_delta_mock_5y.parquet 已经是长表（value_number 为数值列），这里优先处理。
    """
    # 先做列名统一（可按需增补）
    rename_map = {
        "province": "region",
        "city": "region",
        "area": "region",
        "地区": "region",
        "region": "region",

        "年份": "year",
        "year": "year",

        "指标": "indicator",
        "metric": "indicator",
        "indicator": "indicator",

        "value_number": "value_number",
        "unit": "unit",
        "source": "source",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # A) 你的数据：长表（推荐路径）
    if {"region", "year", "indicator", "value_number"}.issubset(df.columns):
        cols = ["region", "year", "indicator", "value_number"]
        if "unit" in df.columns:
            cols.append("unit")
        if "source" in df.columns:
            cols.append("source")

        out = df[cols].copy()
        out = out.rename(columns={"value_number": "value"})

        out["year"] = pd.to_numeric(out["year"], errors="coerce")
        out["value"] = pd.to_numeric(out["value"], errors="coerce")
        out = out.dropna(subset=["region", "year", "indicator", "value"])

        out["year"] = out["year"].astype(int)
        out["region"] = out["region"].astype(str)
        out["indicator"] = out["indicator"].astype(str)

        if "unit" in out.columns:
            out["unit"] = out["unit"].astype(str)
        else:
            out["unit"] = None

        if "source" in out.columns:
            out["source"] = out["source"].astype(str)
        else:
            out["source"] = None

        return out[["region", "year", "indicator", "value", "unit", "source"]]

    # B) 兜底：宽表（只有 region/year，其它列是指标）
    if {"region", "year"}.issubset(df.columns):
        id_vars = ["region", "year"]
        value_vars = [c for c in df.columns if c not in id_vars]

        # 如果 df 里已经有 value 列，melt 的 value_name 就不能叫 value
        value_name = "value_tmp" if "value" in df.columns else "value"

        out = df.melt(id_vars=id_vars, value_vars=value_vars, var_name="indicator", value_name=value_name)
        out["year"] = pd.to_numeric(out["year"], errors="coerce")
        out[value_name] = pd.to_numeric(out[value_name], errors="coerce")
        out = out.dropna(subset=["region", "year", "indicator", value_name])
        out = out.rename(columns={value_name: "value"})

        out["year"] = out["year"].astype(int)
        out["region"] = out["region"].astype(str)
        out["indicator"] = out["indicator"].astype(str)
        out["unit"] = None
        out["source"] = None
        return out[["region", "year", "indicator", "value", "unit", "source"]]

    raise ValueError(f"Unrecognized schema. Columns={list(df.columns)}")
