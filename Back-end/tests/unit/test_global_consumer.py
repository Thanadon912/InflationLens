import pytest

from app.engines.global_ import consumer as gc
from app.engines.shared.errors import InvalidWeightError
from app.models.enums import Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"
ALL_GEOS = ("USA", "EA", "THA")


class TestArithmeticAggregation:
    def test_matches_manual_weighted_mean(self):
        rates = {"USA": 3.2, "EA": 2.5, "THA": 1.8}
        weights = {"USA": 0.4, "EA": 0.35, "THA": 0.25}
        result = gc.calculate(
            country_headline_rates=rates, country_weights=weights,
            all_geographies=ALL_GEOS, period="2026-06", calculated_at=CALCULATED_AT,
        )
        expected = sum(rates[c] * weights[c] for c in rates)
        assert result.value == pytest.approx(expected)
        assert result.geography == "GLOBAL"

    def test_invariant_to_input_order(self):
        rates = {"USA": 3.2, "EA": 2.5, "THA": 1.8}
        weights = {"USA": 0.4, "EA": 0.35, "THA": 0.25}
        rates_rev = dict(reversed(list(rates.items())))
        weights_rev = dict(reversed(list(weights.items())))
        r1 = gc.calculate(country_headline_rates=rates, country_weights=weights, all_geographies=ALL_GEOS, period="p", calculated_at=CALCULATED_AT)
        r2 = gc.calculate(country_headline_rates=rates_rev, country_weights=weights_rev, all_geographies=ALL_GEOS, period="p", calculated_at=CALCULATED_AT)
        assert r1.value == pytest.approx(r2.value)

    def test_full_coverage_when_all_countries_present(self):
        rates = {"USA": 3.2, "EA": 2.5, "THA": 1.8}
        weights = {"USA": 0.4, "EA": 0.35, "THA": 0.25}
        result = gc.calculate(country_headline_rates=rates, country_weights=weights, all_geographies=ALL_GEOS, period="p", calculated_at=CALCULATED_AT)
        assert result.coverage == Coverage.FULL
        assert result.coverage_report.included_count == 3

    def test_partial_coverage_when_country_missing(self):
        rates = {"USA": 3.2, "EA": 2.5}
        weights = {"USA": 0.55, "EA": 0.45}
        result = gc.calculate(country_headline_rates=rates, country_weights=weights, all_geographies=ALL_GEOS, period="p", calculated_at=CALCULATED_AT)
        assert result.coverage == Coverage.PARTIAL
        assert result.coverage_report.missing_geographies == ("THA",)

    def test_zero_growth_all_countries(self):
        rates = {"USA": 0.0, "EA": 0.0}
        weights = {"USA": 0.5, "EA": 0.5}
        result = gc.calculate(country_headline_rates=rates, country_weights=weights, all_geographies=ALL_GEOS, period="p", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(0.0)

    def test_hyperinflation_country_not_excluded(self):
        rates = {"USA": 3.0, "ARG": 100.0}
        weights = {"USA": 0.9, "ARG": 0.1}
        result = gc.calculate(country_headline_rates=rates, country_weights=weights, all_geographies=("USA", "ARG"), period="p", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(0.9 * 3.0 + 0.1 * 100.0)


class TestGeometricView:
    def test_present_when_relatives_supplied(self):
        rates = {"USA": 3.2, "EA": 2.5}
        weights = {"USA": 0.5, "EA": 0.5}
        relatives = {"USA": 1.003, "EA": 1.002}
        result = gc.calculate(
            country_headline_rates=rates, country_weights=weights,
            all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
            country_price_relatives=relatives,
        )
        comp = next(c for c in result.components if c.key == "geometric_period_relative_percent")
        expected = ((1.003**0.5) * (1.002**0.5) - 1) * 100
        assert comp.value == pytest.approx(expected)

    def test_absent_without_relatives(self):
        rates = {"USA": 3.2, "EA": 2.5}
        weights = {"USA": 0.5, "EA": 0.5}
        result = gc.calculate(country_headline_rates=rates, country_weights=weights, all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT)
        assert not any(c.key == "geometric_period_relative_percent" for c in result.components)


class TestInvalidWeights:
    def test_weights_not_summing_to_one_raises(self):
        rates = {"USA": 3.2, "EA": 2.5}
        weights = {"USA": 0.6, "EA": 0.6}  # sums to 1.2
        with pytest.raises(InvalidWeightError):
            gc.calculate(country_headline_rates=rates, country_weights=weights, all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT)

    def test_mismatched_keys_between_rates_and_weights_raises(self):
        rates = {"USA": 3.2, "EA": 2.5}
        weights = {"USA": 0.5, "THA": 0.5}  # EA/THA mismatch
        with pytest.raises(InvalidWeightError):
            gc.calculate(country_headline_rates=rates, country_weights=weights, all_geographies=ALL_GEOS, period="p", calculated_at=CALCULATED_AT)

    def test_negative_weight_raises(self):
        rates = {"USA": 3.2, "EA": 2.5}
        weights = {"USA": 1.2, "EA": -0.2}
        with pytest.raises(InvalidWeightError):
            gc.calculate(country_headline_rates=rates, country_weights=weights, all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT)

    def test_empty_rates_and_weights_raises(self):
        with pytest.raises(InvalidWeightError):
            gc.calculate(country_headline_rates={}, country_weights={}, all_geographies=(), period="p", calculated_at=CALCULATED_AT)
