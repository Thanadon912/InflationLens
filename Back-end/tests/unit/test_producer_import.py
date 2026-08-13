import pytest

from app.engines.country import producer_import as pi
from app.models.enums import Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"


def cfg():
    return pi.ProducerImportConfig(component_weights={"ppi": 0.4, "import": 0.3, "energy": 0.2, "commodity": 0.1})


class TestBasicRates:
    def test_ppi_and_import_match_manual_yoy(self):
        result = pi.calculate(
            ppi_current=110.0, ppi_prior_year=100.0,
            import_price_current=108.0, import_price_prior_year=100.0,
            energy_inflation_percent=10.0, commodity_inflation_percent=5.0,
            config=cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        ppi = next(c for c in result.components if c.key == "ppi_inflation")
        imp = next(c for c in result.components if c.key == "import_inflation")
        assert ppi.value == pytest.approx(10.0)
        assert imp.value == pytest.approx(8.0)

    def test_upstream_pressure_basket_matches_manual_weighted_mean(self):
        result = pi.calculate(
            ppi_current=110.0, ppi_prior_year=100.0,
            import_price_current=108.0, import_price_prior_year=100.0,
            energy_inflation_percent=10.0, commodity_inflation_percent=5.0,
            config=cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        expected = 0.4 * 10.0 + 0.3 * 8.0 + 0.2 * 10.0 + 0.1 * 5.0
        assert result.value == pytest.approx(expected)
        assert result.unit.value == "percent_yoy"

    def test_zero_growth(self):
        result = pi.calculate(
            ppi_current=100.0, ppi_prior_year=100.0,
            import_price_current=100.0, import_price_prior_year=100.0,
            energy_inflation_percent=0.0, commodity_inflation_percent=0.0,
            config=cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value == pytest.approx(0.0)

    def test_deflation_case(self):
        result = pi.calculate(
            ppi_current=95.0, ppi_prior_year=100.0,
            import_price_current=97.0, import_price_prior_year=100.0,
            energy_inflation_percent=-5.0, commodity_inflation_percent=-2.0,
            config=cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value < 0


class TestExchangeRatePassThrough:
    def test_exact_matches_multiplicative_formula(self):
        result = pi.calculate(
            ppi_current=100.0, ppi_prior_year=100.0,
            import_price_current=100.0, import_price_prior_year=100.0,
            energy_inflation_percent=0.0, commodity_inflation_percent=0.0,
            config=cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            foreign_price_growth_percent=5.0, exchange_rate_growth_percent=3.0,
        )
        exact = next(c for c in result.components if c.key == "exchange_rate_pass_through_exact")
        expected = ((1.05 * 1.03) - 1) * 100
        assert exact.value == pytest.approx(expected)

    def test_approx_is_simple_sum(self):
        result = pi.calculate(
            ppi_current=100.0, ppi_prior_year=100.0,
            import_price_current=100.0, import_price_prior_year=100.0,
            energy_inflation_percent=0.0, commodity_inflation_percent=0.0,
            config=cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            foreign_price_growth_percent=5.0, exchange_rate_growth_percent=3.0,
        )
        approx = next(c for c in result.components if c.key == "exchange_rate_pass_through_approx")
        assert approx.value == pytest.approx(8.0)

    def test_missing_fx_data_marks_partial(self):
        result = pi.calculate(
            ppi_current=100.0, ppi_prior_year=100.0,
            import_price_current=100.0, import_price_prior_year=100.0,
            energy_inflation_percent=0.0, commodity_inflation_percent=0.0,
            config=cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.coverage == Coverage.PARTIAL
        assert not any(c.key.startswith("exchange_rate_pass_through") for c in result.components)


class TestUpstreamPressureScore:
    def test_score_marked_correctly(self):
        result = pi.calculate(
            ppi_current=110.0, ppi_prior_year=100.0,
            import_price_current=108.0, import_price_prior_year=100.0,
            energy_inflation_percent=10.0, commodity_inflation_percent=5.0,
            config=cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            upp_standardization_window=[2.0, 3.0, 4.0, 5.0, 6.0],
        )
        score = next(c for c in result.components if c.key == "upstream_pressure_score")
        assert score.is_score is True
        assert score.unit.value == "standard_deviation_score"

    def test_no_score_without_window(self):
        result = pi.calculate(
            ppi_current=110.0, ppi_prior_year=100.0,
            import_price_current=108.0, import_price_prior_year=100.0,
            energy_inflation_percent=10.0, commodity_inflation_percent=5.0,
            config=cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert not any(c.key == "upstream_pressure_score" for c in result.components)
