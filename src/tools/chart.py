"""Chart generation tools for LongDelta-AI.

This module provides tools to generate Plotly chart configurations
that can be rendered by the frontend.
"""
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ChartConfig(BaseModel):
    """Plotly chart configuration."""
    type: str = Field(..., description="Chart type: bar, pie, line")
    data: list[dict[str, Any]] = Field(..., description="Chart data records")
    layout: dict[str, Any] = Field(default_factory=dict, description="Layout options")
    title: str = Field(default="", description="Chart title")

    # Column mappings
    x_column: str | None = Field(default=None, description="X-axis column name")
    y_column: str | None = Field(default=None, description="Y-axis column name")
    names_column: str | None = Field(default=None, description="Names column for pie chart")
    values_column: str | None = Field(default=None, description="Values column for pie chart")


class ChartResponse(BaseModel):
    """Chart generation response with Plotly config."""
    chart: ChartConfig
    plotly_json: dict[str, Any] = Field(..., description="Plotly.js compatible JSON")


def create_bar_chart(
    data: list[dict[str, Any]],
    x_column: str,
    y_column: str,
    title: str = ""
) -> ChartConfig:
    """Create a bar chart configuration."""
    return ChartConfig(
        type="bar",
        data=data,
        title=title,
        x_column=x_column,
        y_column=y_column,
        layout={
            "xaxis": {"title": x_column},
            "yaxis": {"title": y_column},
            "barmode": "group"
        }
    )


def create_pie_chart(
    data: list[dict[str, Any]],
    names_column: str,
    values_column: str,
    title: str = ""
) -> ChartConfig:
    """Create a pie chart configuration."""
    return ChartConfig(
        type="pie",
        data=data,
        title=title,
        names_column=names_column,
        values_column=values_column,
        layout={
            "showlegend": True,
            "legend": {"orientation": "h", "y": -0.1}
        }
    )


def create_line_chart(
    data: list[dict[str, Any]],
    x_column: str,
    y_column: str,
    title: str = ""
) -> ChartConfig:
    """Create a line chart configuration."""
    return ChartConfig(
        type="line",
        data=data,
        title=title,
        x_column=x_column,
        y_column=y_column,
        layout={
            "xaxis": {"title": x_column},
            "yaxis": {"title": y_column},
            "hovermode": "x unified"
        }
    )


def chart_config_to_plotly_json(config: ChartConfig) -> dict[str, Any]:
    """Convert ChartConfig to Plotly.js compatible JSON."""
    # Build Plotly traces based on chart type
    traces = []

    if config.type == "bar":
        traces.append({
            "type": "bar",
            "x": [d.get(config.x_column, "") for d in config.data],
            "y": [d.get(config.y_column, 0) for d in config.data],
            "marker": {
                "color": "#3b82f6",
                "opacity": 0.8
            }
        })
    elif config.type == "pie":
        traces.append({
            "type": "pie",
            "labels": [d.get(config.names_column, "") for d in config.data],
            "values": [d.get(config.values_column, 0) for d in config.data],
            "textinfo": "label+percent",
            "hole": 0.4
        })
    elif config.type == "line":
        traces.append({
            "type": "scatter",
            "mode": "lines+markers",
            "x": [d.get(config.x_column, "") for d in config.data],
            "y": [d.get(config.y_column, 0) for d in config.data],
            "line": {"color": "#10b981", "width": 2},
            "marker": {"size": 8}
        })

    return {
        "data": traces,
        "layout": {
            "title": config.title,
            **config.layout
        }
    }


@tool
def generate_chart(
    chart_type: str,
    data: list[dict[str, Any]],
    title: str = "",
    x_column: str | None = None,
    y_column: str | None = None,
    names_column: str | None = None,
    values_column: str | None = None
) -> dict[str, Any]:
    """
    Generate a Plotly chart configuration for frontend rendering.

    Args:
        chart_type: Type of chart (bar, pie, line)
        data: List of data records
        title: Chart title
        x_column: Column name for X-axis (bar/line)
        y_column: Column name for Y-axis (bar/line)
        names_column: Column name for pie chart names
        values_column: Column name for pie chart values

    Returns:
        Dict containing chart config and Plotly JSON
    """
    # Create chart config
    if chart_type == "pie":
        if not names_column or not values_column:
            # Auto-detect columns
            if data:
                names_column = names_column or "region"
                values_column = values_column or "value"
        config = create_pie_chart(
            data=data,
            names_column=names_column or "name",
            values_column=values_column or "value",
            title=title
        )
    elif chart_type == "line":
        config = create_line_chart(
            data=data,
            x_column=x_column or "year",
            y_column=y_column or "value",
            title=title
        )
    else:  # bar or default
        config = create_bar_chart(
            data=data,
            x_column=x_column or "region",
            y_column=y_column or "value",
            title=title
        )

    # Convert to Plotly JSON
    plotly_json = chart_config_to_plotly_json(config)

    return {
        "chart": config.model_dump(),
        "plotly_json": plotly_json
    }


@tool
def generate_regional_comparison_chart(
    region_a: str,
    region_b: str,
    indicator: str,
    year: int,
    data: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Generate a comparison bar chart between two regions.

    Args:
        region_a: First region name
        region_b: Second region name
        indicator: Economic indicator name
        year: Year for comparison
        data: Data records for both regions

    Returns:
        Chart configuration for regional comparison
    """
    title = f"{year}年{indicator}对比: {region_a} vs {region_b}"

    # Filter and format data
    chart_data = []
    for record in data:
        if record.get("region") in [region_a, region_b]:
            chart_data.append({
                "region": record.get("region", ""),
                "value": record.get("value", 0),
                "indicator": record.get("indicator", "")
            })

    return generate_chart.invoke({
        "chart_type": "bar",
        "data": chart_data,
        "title": title,
        "x_column": "region",
        "y_column": "value"
    })


@tool
def generate_trend_line_chart(
    region: str,
    indicator: str,
    start_year: int,
    end_year: int,
    data: list[dict[str, Any]]
) -> dict[str, Any]:
    """
    Generate a line chart showing trend over years.

    Args:
        region: Region name
        indicator: Economic indicator
        start_year: Start year
        end_year: End year
        data: Multi-year data records

    Returns:
        Chart configuration for trend visualization
    """
    title = f"{region}{indicator}趋势 ({start_year}-{end_year})"

    # Filter and sort data by year
    chart_data = []
    for record in data:
        if record.get("region") == region and record.get("indicator") == indicator:
            year = record.get("year", 0)
            if start_year <= year <= end_year:
                chart_data.append({
                    "year": year,
                    "value": record.get("value", 0)
                })

    # Sort by year
    chart_data.sort(key=lambda x: x["year"])

    return generate_chart.invoke({
        "chart_type": "line",
        "data": chart_data,
        "title": title,
        "x_column": "year",
        "y_column": "value"
    })
