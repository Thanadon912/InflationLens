import pytest

from app.engines.shared.coverage import (
    build_coverage_report,
    check_coverage_threshold,
    coverage_percent,
    renormalize_weights,
)
from app.engines.shared.errors import CoverageThresholdError, InvalidWeightError


class TestRenormalizeWeights:
    def test_full_coverage_returns_original_weights(self):
        weights = {"USA": 0.4, "EA": 0.3, "THA": 0.3}
        result = renormalize_weights(weights, ["USA", "EA", "THA"])
        assert result == pytest.approx(weights)

    def test_partial_coverage_renormalizes_to_sum_one(self):
        weights = {"USA": 0.4, "EA": 0.3, "THA": 0.3}
        result = renormalize_weights(weights, ["USA", "EA"])
        assert sum(result.values()) == pytest.approx(1.0)
        # relative proportions preserved
        assert result["USA"] / result["EA"] == pytest.approx(0.4 / 0.3)

    def test_unknown_available_key_raises(self):
        with pytest.raises(InvalidWeightError):
            renormalize_weights({"USA": 1.0}, ["EA"])

    def test_zero_total_weight_raises(self):
        with pytest.raises(InvalidWeightError):
            renormalize_weights({"USA": 0.0, "EA": 0.0}, ["USA", "EA"])

    def test_single_country_full_weight(self):
        result = renormalize_weights({"USA": 0.5, "EA": 0.5}, ["USA"])
        assert result == {"USA": 1.0}


class TestCoveragePercent:
    def test_full_coverage(self):
        assert coverage_percent(100.0, 100.0) == pytest.approx(100.0)

    def test_partial_coverage(self):
        assert coverage_percent(85.0, 100.0) == pytest.approx(85.0)

    def test_zero_total_raises(self):
        with pytest.raises(InvalidWeightError):
            coverage_percent(10.0, 0.0)


class TestCheckCoverageThreshold:
    def test_above_threshold_passes(self):
        check_coverage_threshold(90.0, 85.0, context="test")

    def test_exactly_at_threshold_passes(self):
        check_coverage_threshold(85.0, 85.0, context="test")

    def test_below_threshold_raises(self):
        with pytest.raises(CoverageThresholdError):
            check_coverage_threshold(80.0, 85.0, context="test")


class TestBuildCoverageReport:
    def test_full_coverage(self):
        report = build_coverage_report(
            all_geographies=["USA", "EA", "THA"],
            included_geographies=["USA", "EA", "THA"],
            population_by_geo={"USA": 331.0, "EA": 340.0, "THA": 70.0},
        )
        assert report.included_count == 3
        assert report.missing_geographies == ()
        assert report.population_coverage_percent == pytest.approx(100.0)

    def test_partial_coverage_reports_missing(self):
        report = build_coverage_report(
            all_geographies=["USA", "EA", "THA"],
            included_geographies=["USA", "EA"],
            population_by_geo={"USA": 331.0, "EA": 340.0, "THA": 70.0},
        )
        assert report.missing_geographies == ("THA",)
        expected = (331.0 + 340.0) / (331.0 + 340.0 + 70.0) * 100
        assert report.population_coverage_percent == pytest.approx(expected)

    def test_no_measure_data_gives_none_percent(self):
        report = build_coverage_report(
            all_geographies=["USA", "EA"], included_geographies=["USA"]
        )
        assert report.population_coverage_percent is None
        assert report.gdp_ppp_coverage_percent is None

    def test_renormalized_flag_set_when_weights_differ(self):
        report = build_coverage_report(
            all_geographies=["USA", "EA"],
            included_geographies=["USA"],
            original_weights={"USA": 0.5, "EA": 0.5},
            adjusted_weights={"USA": 1.0},
        )
        assert report.weights_renormalized is True

    def test_not_renormalized_when_no_original_weights_given(self):
        report = build_coverage_report(all_geographies=["USA"], included_geographies=["USA"])
        assert report.weights_renormalized is False
