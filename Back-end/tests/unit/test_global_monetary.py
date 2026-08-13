import pytest

from app.engines.global_ import monetary as gm

CALCULATED_AT = "2026-08-02T12:00:00Z"


class TestGlobalMonetary:
    def test_gdp_ppp_weighted_matches_manual(self):
        rates = {"USA": 6.0, "EA": 4.0}
        weights = {"USA": 0.5, "EA": 0.5}
        result = gm.calculate(
            country_money_growth_rates=rates, gdp_ppp_weights=weights,
            all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
        )
        assert result.value == pytest.approx(5.0)
        assert result.metadata["currency_conversion_applied"] is False

    def test_geometric_component_present(self):
        rates = {"USA": 6.0, "EA": 4.0}
        weights = {"USA": 0.5, "EA": 0.5}
        result = gm.calculate(country_money_growth_rates=rates, gdp_ppp_weights=weights, all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT)
        geo = next(c for c in result.components if c.key == "geometric")
        expected = ((1.06**0.5) * (1.04**0.5) - 1) * 100
        assert geo.value == pytest.approx(expected)

    def test_consumption_ppp_alternative_optional(self):
        rates = {"USA": 6.0, "EA": 4.0}
        gdp_weights = {"USA": 0.5, "EA": 0.5}
        cons_weights = {"USA": 0.3, "EA": 0.7}
        result = gm.calculate(
            country_money_growth_rates=rates, gdp_ppp_weights=gdp_weights,
            all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT,
            consumption_ppp_weights=cons_weights,
        )
        alt = next(c for c in result.components if c.key == "consumption_ppp_weighted")
        assert alt.value == pytest.approx(0.3 * 6.0 + 0.7 * 4.0)

    def test_zero_expansion(self):
        rates = {"USA": 0.0, "EA": 0.0}
        weights = {"USA": 0.5, "EA": 0.5}
        result = gm.calculate(country_money_growth_rates=rates, gdp_ppp_weights=weights, all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(0.0)

    def test_contraction_case(self):
        rates = {"USA": -2.0, "EA": -1.0}
        weights = {"USA": 0.5, "EA": 0.5}
        result = gm.calculate(country_money_growth_rates=rates, gdp_ppp_weights=weights, all_geographies=("USA", "EA"), period="p", calculated_at=CALCULATED_AT)
        assert result.value < 0
