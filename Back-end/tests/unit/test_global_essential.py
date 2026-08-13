import pytest

from app.engines.global_ import essential as ge

CALCULATED_AT = "2026-08-02T12:00:00Z"


class TestGlobalEssential:
    def test_consumption_weighted_matches_manual(self):
        rates = {"USA": 4.0, "EA": 3.0}
        weights = {"USA": 0.6, "EA": 0.4}
        result = ge.calculate(
            country_essential_rates=rates, consumption_ppp_weights=weights,
            all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
        )
        assert result.value == pytest.approx(0.6 * 4.0 + 0.4 * 3.0)

    def test_population_weighted_alternative(self):
        rates = {"USA": 4.0, "EA": 3.0}
        cons_weights = {"USA": 0.6, "EA": 0.4}
        pop_weights = {"USA": 0.3, "EA": 0.7}
        result = ge.calculate(
            country_essential_rates=rates, consumption_ppp_weights=cons_weights,
            all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
            population_weights=pop_weights,
        )
        pop_comp = next(c for c in result.components if c.key == "population_weighted")
        assert pop_comp.value == pytest.approx(0.3 * 4.0 + 0.7 * 3.0)
        assert pop_comp.value != pytest.approx(result.value)

    def test_zero_growth(self):
        rates = {"USA": 0.0, "EA": 0.0}
        weights = {"USA": 0.5, "EA": 0.5}
        result = ge.calculate(country_essential_rates=rates, consumption_ppp_weights=weights, all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(0.0)
