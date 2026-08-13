import pytest

from app.models.coverage import CoverageReport
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance


def make_result(**overrides):
    defaults = dict(
        indicator_id="headline_consumer_inflation",
        geography="USA",
        period="2026-06",
        value=3.2,
        unit=Unit.PERCENT_YOY,
        method="index_year_over_year",
        methodology_version="1.0.0",
        input_series=(InputProvenance(provider="bls", series_id="CUUR0000SA0"),),
        coverage=Coverage.FULL,
        confidence=Confidence.HIGH,
        is_estimated=False,
        warnings=(),
        calculated_at="2026-08-02T12:00:00Z",
    )
    defaults.update(overrides)
    return IndicatorResult(**defaults)


class TestComponent:
    def test_score_requires_score_unit(self):
        with pytest.raises(ValueError):
            Component(key="hps", label="Housing Pressure Score", value=1.2, unit=Unit.PERCENT_YOY, is_score=True)

    def test_score_with_correct_unit_ok(self):
        c = Component(
            key="hps",
            label="Housing Pressure Score",
            value=1.2,
            unit=Unit.STANDARD_DEVIATION_SCORE,
            is_score=True,
        )
        assert c.is_score is True

    def test_to_dict(self):
        c = Component(key="rent", label="Rent Inflation", value=4.1, unit=Unit.PERCENT_YOY)
        d = c.to_dict()
        assert d["key"] == "rent"
        assert d["value"] == 4.1
        assert d["unit"] == "percent_yoy"


class TestIndicatorResultContract:
    def test_matches_documented_required_fields(self):
        result = make_result()
        d = result.to_dict()
        required = {
            "indicator_id",
            "geography",
            "period",
            "value",
            "unit",
            "method",
            "methodology_version",
            "input_series",
            "coverage",
            "confidence",
            "is_estimated",
            "warnings",
            "calculated_at",
        }
        assert required.issubset(d.keys())

    def test_value_requires_unit(self):
        with pytest.raises(ValueError):
            make_result(value=3.2, unit=None)

    def test_unavailable_requires_none_value(self):
        with pytest.raises(ValueError):
            make_result(coverage=Coverage.UNAVAILABLE, value=3.2)

    def test_none_value_allowed_when_unavailable(self):
        result = make_result(coverage=Coverage.UNAVAILABLE, value=None, unit=None)
        assert result.value is None

    def test_none_value_allowed_with_unit_none_even_if_full(self):
        # A value of None with coverage=full is not a documented case but
        # must not crash; unit is optional whenever value is None.
        result = make_result(value=None, unit=None)
        assert result.value is None


class TestUnavailableFactory:
    def test_produces_unavailable_result(self):
        result = IndicatorResult.unavailable(
            indicator_id="broad_money_expansion",
            geography="USA",
            period="2026-06",
            method="unavailable",
            methodology_version="1.0.0",
            calculated_at="2026-08-02T12:00:00Z",
            reason="missing required input: broad_money_level",
        )
        assert result.value is None
        assert result.coverage == Coverage.UNAVAILABLE
        assert result.confidence == Confidence.LOW
        assert "missing required input" in result.warnings[0]

    def test_never_returns_zero_for_failed_calculation(self):
        result = IndicatorResult.unavailable(
            indicator_id="x",
            geography="USA",
            period="2026-06",
            method="unavailable",
            methodology_version="1.0.0",
            calculated_at="2026-08-02T12:00:00Z",
            reason="test",
        )
        assert result.value != 0
        assert result.value is None


class TestComponentsAndCoverageReport:
    def test_multi_value_indicator_keeps_all_components(self):
        components = (
            Component(key="gdp_deflator", label="GDP Deflator Inflation", value=3.8, unit=Unit.PERCENT_YOY),
            Component(
                key="domestic_demand_deflator",
                label="Domestic Demand Deflator Inflation",
                value=4.2,
                unit=Unit.PERCENT_YOY,
            ),
        )
        result = make_result(value=None, unit=None, components=components)
        assert len(result.components) == 2
        assert result.to_dict()["components"][1]["value"] == 4.2

    def test_coverage_report_serializes(self):
        report = CoverageReport(
            included_geographies=("USA", "EA"),
            missing_geographies=("THA",),
            population_coverage_percent=96.8,
            weights_renormalized=True,
        )
        result = make_result(coverage_report=report)
        d = result.to_dict()
        assert d["coverage_report"]["included_countries"] == 2
        assert d["coverage_report"]["missing_geographies"] == ["THA"]
        assert d["coverage_report"]["weights_renormalized"] is True

    def test_metadata_round_trips(self):
        result = make_result(metadata={"selected_method": "weighted_median"})
        assert result.to_dict()["metadata"]["selected_method"] == "weighted_median"
