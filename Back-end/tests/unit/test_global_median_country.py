import pytest

from app.engines.global_ import median_country as mc
from app.engines.shared.errors import DataQualityError, InvalidWeightError

CALCULATED_AT = "2026-08-02T12:00:00Z"
ALL_GEOS = ("A", "B", "C", "D", "E")


class TestMedianAndSpread:
    def test_odd_count_median(self):
        rates = {"A": 1.0, "B": 3.0, "C": 2.0}
        result = mc.calculate(country_rates=rates, all_geographies=("A", "B", "C"), period="p", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(2.0)

    def test_even_count_median_averages_middle_two(self):
        rates = {"A": 1.0, "B": 2.0, "C": 3.0, "D": 4.0}
        result = mc.calculate(country_rates=rates, all_geographies=("A", "B", "C", "D"), period="p", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(2.5)

    def test_order_invariance(self):
        rates = {"A": 5.0, "B": 1.0, "C": 3.0}
        rates_rev = dict(reversed(list(rates.items())))
        r1 = mc.calculate(country_rates=rates, all_geographies=("A", "B", "C"), period="p", calculated_at=CALCULATED_AT)
        r2 = mc.calculate(country_rates=rates_rev, all_geographies=("A", "B", "C"), period="p", calculated_at=CALCULATED_AT)
        assert r1.value == pytest.approx(r2.value)

    def test_min_max_p25_p75_present(self):
        rates = {c: float(i) for i, c in enumerate("ABCDE", start=1)}
        result = mc.calculate(country_rates=rates, all_geographies=ALL_GEOS, period="p", calculated_at=CALCULATED_AT)
        vals = {c.key: c.value for c in result.components}
        assert vals["min"] == pytest.approx(1.0)
        assert vals["max"] == pytest.approx(5.0)
        assert vals["count"] == pytest.approx(5.0)

    def test_hyperinflation_not_excluded(self):
        rates = {"A": 2.0, "B": 3.0, "C": 4.0, "D": 5.0, "E": 50000.0}
        result = mc.calculate(country_rates=rates, all_geographies=ALL_GEOS, period="p", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(4.0)
        vals = {c.key: c.value for c in result.components}
        assert vals["max"] == pytest.approx(50000.0)

    def test_weighted_median_optional(self):
        rates = {"A": 1.0, "B": 5.0, "C": 9.0}
        weights = {"A": 0.3, "B": 0.3, "C": 0.4}
        result = mc.calculate(country_rates=rates, all_geographies=("A", "B", "C"), period="p", calculated_at=CALCULATED_AT, country_weights=weights)
        wm = next(c for c in result.components if c.key == "weighted_median")
        assert wm.value == pytest.approx(5.0)

    def test_no_weighted_median_without_weights(self):
        rates = {"A": 1.0, "B": 5.0, "C": 9.0}
        result = mc.calculate(country_rates=rates, all_geographies=("A", "B", "C"), period="p", calculated_at=CALCULATED_AT)
        assert not any(c.key == "weighted_median" for c in result.components)

    def test_partial_coverage_when_countries_missing(self):
        rates = {"A": 1.0, "B": 2.0}
        result = mc.calculate(country_rates=rates, all_geographies=ALL_GEOS, period="p", calculated_at=CALCULATED_AT)
        assert result.coverage_report.missing_geographies == ("C", "D", "E")


class TestInvalidInputs:
    def test_empty_country_rates_raises(self):
        with pytest.raises(DataQualityError):
            mc.calculate(country_rates={}, all_geographies=(), period="p", calculated_at=CALCULATED_AT)

    def test_weighted_median_with_mismatched_weight_keys_raises(self):
        rates = {"A": 1.0, "B": 5.0}
        weights = {"A": 0.5, "C": 0.5}  # B/C mismatch
        with pytest.raises(InvalidWeightError):
            mc.calculate(country_rates=rates, all_geographies=("A", "B"), period="p", calculated_at=CALCULATED_AT, country_weights=weights)

    def test_weighted_median_with_weights_not_summing_to_one_raises(self):
        rates = {"A": 1.0, "B": 5.0}
        weights = {"A": 0.5, "B": 0.9}
        with pytest.raises(InvalidWeightError):
            mc.calculate(country_rates=rates, all_geographies=("A", "B"), period="p", calculated_at=CALCULATED_AT, country_weights=weights)
