import pytest

from app.engines.country import purchasing_power as pp
from app.models.enums import Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"


class TestRealWageGrowth:
    def test_headline_exact_matches_manual_formula(self):
        result = pp.calculate(
            nominal_wage_growth_percent=5.0, headline_inflation_percent=3.0,
            essential_inflation_percent=4.0, wage_measure="mean", income_definition="gross",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        expected = ((1.05 / 1.03) - 1) * 100
        assert result.value == pytest.approx(expected)

    def test_approx_matches_subtraction(self):
        result = pp.calculate(
            nominal_wage_growth_percent=5.0, headline_inflation_percent=3.0,
            essential_inflation_percent=4.0, wage_measure="mean", income_definition="gross",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        approx = next(c for c in result.components if c.key == "real_wage_headline_approx")
        assert approx.value == pytest.approx(2.0)

    def test_dual_reporting_present_for_both_headline_and_essential(self):
        result = pp.calculate(
            nominal_wage_growth_percent=5.0, headline_inflation_percent=3.0,
            essential_inflation_percent=6.0, wage_measure="mean", income_definition="gross",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        keys = {c.key for c in result.components}
        assert "real_wage_essential_exact" in keys
        # squeeze visible under essential costs even if headline shows a gain
        essential_squeeze = next(c for c in result.components if c.key == "purchasing_power_squeeze_essential")
        headline_squeeze = next(c for c in result.components if c.key == "purchasing_power_squeeze_headline")
        assert essential_squeeze.value > headline_squeeze.value

    def test_zero_inflation_real_equals_nominal(self):
        result = pp.calculate(
            nominal_wage_growth_percent=4.0, headline_inflation_percent=0.0,
            essential_inflation_percent=0.0, wage_measure="mean", income_definition="gross",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value == pytest.approx(4.0)

    def test_negative_real_wage_when_inflation_exceeds_wages(self):
        result = pp.calculate(
            nominal_wage_growth_percent=2.0, headline_inflation_percent=5.0,
            essential_inflation_percent=6.0, wage_measure="mean", income_definition="gross",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value < 0


class TestSqueeze:
    def test_positive_squeeze_when_prices_outpace_income(self):
        result = pp.calculate(
            nominal_wage_growth_percent=2.0, headline_inflation_percent=5.0,
            essential_inflation_percent=5.0, wage_measure="mean", income_definition="gross",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        squeeze = next(c for c in result.components if c.key == "purchasing_power_squeeze_headline")
        assert squeeze.value == pytest.approx(3.0)

    def test_negative_squeeze_when_income_outpaces_prices(self):
        result = pp.calculate(
            nominal_wage_growth_percent=6.0, headline_inflation_percent=3.0,
            essential_inflation_percent=3.0, wage_measure="mean", income_definition="gross",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        squeeze = next(c for c in result.components if c.key == "purchasing_power_squeeze_headline")
        assert squeeze.value < 0


class TestDisposableIncome:
    def test_present_when_provided(self):
        result = pp.calculate(
            nominal_wage_growth_percent=5.0, headline_inflation_percent=3.0,
            essential_inflation_percent=4.0, wage_measure="mean", income_definition="gross",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            disposable_income_growth_percent=4.5,
        )
        assert result.coverage == Coverage.FULL
        assert any(c.key == "real_disposable_income_growth" for c in result.components)

    def test_absent_marks_partial(self):
        result = pp.calculate(
            nominal_wage_growth_percent=5.0, headline_inflation_percent=3.0,
            essential_inflation_percent=4.0, wage_measure="mean", income_definition="gross",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.coverage == Coverage.PARTIAL


class TestDefinitionPreservation:
    def test_wage_measure_and_income_definition_recorded(self):
        result = pp.calculate(
            nominal_wage_growth_percent=5.0, headline_inflation_percent=3.0,
            essential_inflation_percent=4.0, wage_measure="median", income_definition="disposable",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.metadata["wage_measure"] == "median"
        assert result.metadata["income_definition"] == "disposable"
