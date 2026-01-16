"""Tests for tool functions."""
from __future__ import annotations

import pytest

from src.tools.definitions import (
    GrowthRateResponse,
    RegionalDataPoint,
    RegionalDataResponse,
    calculate_growth_rate,
    get_regional_data,
)
from src.tools.implementation import growth_rate, load_dataset, query_regional_data
from src.tools.parse import ParsedQuery, parse_query


class TestDataLoading:
    """Test data loading and preprocessing."""

    def test_load_dataset_exists(self):
        """Test that dataset file exists and can be loaded."""
        df = load_dataset()
        assert df is not None
        assert len(df) > 0

    def test_load_dataset_columns(self):
        """Test that dataset has required columns."""
        df = load_dataset()
        required_cols = {"region", "year", "indicator", "value"}
        assert required_cols.issubset(df.columns)

    def test_load_dataset_types(self):
        """Test that dataset columns have correct types."""
        df = load_dataset()
        assert df["region"].dtype == "object"
        assert df["year"].dtype == "int64"
        assert df["value"].dtype == "float64"


class TestGrowthRate:
    """Test growth rate calculation."""

    def test_growth_rate_normal(self):
        """Test normal growth rate calculation."""
        result = growth_rate(current=105, previous=100)
        assert result == 0.05

    def test_growth_rate_negative(self):
        """Test negative growth rate calculation."""
        result = growth_rate(current=90, previous=100)
        assert result == -0.10

    def test_growth_rate_zero_previous(self):
        """Test that division by zero raises error."""
        with pytest.raises(ValueError):
            growth_rate(current=100, previous=0)

    def test_growth_rate_response_model(self):
        """Test GrowthRateResponse Pydantic model."""
        response = GrowthRateResponse(growth_rate=0.05)
        assert response.growth_rate == 0.05
        assert response.model_dump() == {"growth_rate": 0.05}


class TestRegionalData:
    """Test regional data queries."""

    def test_query_regional_data(self):
        """Test querying regional data returns list of dicts."""
        # Use a region that likely exists in the test data
        df = load_dataset()
        regions = df["region"].unique()
        if len(regions) > 0:
            test_region = regions[0]
            result = query_regional_data(
                region=test_region,
                year=2023,
                indicators=["GDP"]
            )
            assert isinstance(result, list)

    def test_regional_data_point_model(self):
        """Test RegionalDataPoint Pydantic model."""
        point = RegionalDataPoint(
            region="安徽",
            year=2023,
            indicator="GDP",
            value=45000.0,
            unit="亿元",
            source="统计局"
        )
        assert point.region == "安徽"
        assert point.year == 2023
        assert point.indicator == "GDP"

    def test_regional_data_response_model(self):
        """Test RegionalDataResponse Pydantic model."""
        data = [
            RegionalDataPoint(
                region="安徽",
                year=2023,
                indicator="GDP",
                value=45000.0
            )
        ]
        response = RegionalDataResponse(data=data)
        assert len(response.data) == 1
        assert response.data[0].region == "安徽"
        assert isinstance(response.model_dump(), dict)


class TestParseQuery:
    """Test query parsing."""

    def test_parse_query_with_region_and_years(self):
        """Test parsing question with region and years."""
        result = parse_query.invoke({"question": "安徽2023年GDP对比2022年"})
        assert isinstance(result, ParsedQuery)
        assert result.regions[0] == "安徽"
        assert result.year_current == 2023
        assert result.year_previous == 2022
        assert result.indicator == "GDP"

    def test_parse_query_with_cpi(self):
        """Test parsing question with CPI indicator."""
        result = parse_query.invoke({"question": "上海2023年CPI数据"})
        assert result.indicator == "CPI"

    def test_parse_query_infers_previous_year(self):
        """Test that previous year is inferred when not provided."""
        result = parse_query.invoke({"question": "江苏2023年GDP"})
        assert result.year_previous == 2022

    def test_parse_query_raises_on_missing_region(self):
        """Test that missing region raises ValueError."""
        with pytest.raises(ValueError):
            parse_query.invoke({"question": "2023年GDP增长"})


class TestToolFunctions:
    """Test tool functions return Pydantic models."""

    def test_get_regional_data_returns_model(self):
        """Test get_regional_data returns RegionalDataResponse."""
        df = load_dataset()
        regions = df["region"].unique()
        if len(regions) > 0:
            result = get_regional_data.invoke({
                "region": regions[0],
                "year": 2023,
                "indicators": ["GDP"]
            })
            assert isinstance(result, RegionalDataResponse)

    def test_calculate_growth_rate_returns_model(self):
        """Test calculate_growth_rate returns GrowthRateResponse."""
        result = calculate_growth_rate.invoke({"current": 105.0, "previous": 100.0})
        assert isinstance(result, GrowthRateResponse)
        assert result.growth_rate == 0.05
