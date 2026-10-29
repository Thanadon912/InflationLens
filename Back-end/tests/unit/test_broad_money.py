import pytest

from app.engines.country import broad_money as bm
from app.models.enums import Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"


class TestBasicGrowth:
    def test_matches_manual_yoy(self):
        result = bm.calculate(
            money_current=21500.0, money_prior_year=20000.0, aggregate_name="M2",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        expected = (21500.0 / 20000.0 - 1) * 100
        assert result.value == pytest.approx(expected)
        assert result.unit.value == "percent_yoy"
        assert result.metadata["label"] == "Broad Money Expansion"
        assert result.metadata["aggregate_name"] == "M2"

    def test_never_labeled_as_inflation(self):
        result = bm.calculate(
            money_current=21500.0, money_prior_year=20000.0, aggregate_name="M2",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert "inflation" not in result.metadata["label"].lower()

    def test_zero_growth(self):
        result = bm.calculate(
            money_current=20000.0, money_prior_year=20000.0, aggregate_name="M2",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value == pytest.approx(0.0)

    def test_negative_growth_contraction(self):
        result = bm.calculate(
            money_current=19000.0, money_prior_year=20000.0, aggregate_name="M2",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value < 0

    def test_extreme_expansion(self):
        result = bm.calculate(
            money_current=200000.0, money_prior_year=20000.0, aggregate_name="M2",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value == pytest.approx(900.0)


class TestPerCapita:
    def test_matches_manual_formula(self):
        result = bm.calculate(
            money_current=21500.0, money_prior_year=20000.0, aggregate_name="M2",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            population_current=331.0, population_prior_year=329.0,
        )
        pc_current = 21500.0 / 331.0
        pc_prior = 20000.0 / 329.0
        expected = (pc_current / pc_prior - 1) * 100
        comp = next(c for c in result.components if c.key == "per_capita_growth")
        assert comp.value == pytest.approx(expected)

    @pytest.mark.parametrize(
        "pop_kwargs",
        [
            {},
            {"population_current": 331.0},
            {"population_prior_year": 329.0},
        ],
    )
    def test_missing_or_partial_population_marks_partial_without_crashing(self, pop_kwargs):
        result = bm.calculate(
            money_current=21500.0, money_prior_year=20000.0, aggregate_name="M2",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            **pop_kwargs,
        )
        assert result.coverage == Coverage.PARTIAL
        assert not any(c.key == "per_capita_growth" for c in result.components)
        assert any("per_capita_growth unavailable" in w for w in result.warnings)


class TestMoneyToOutputRatio:
    def test_ratio_and_approx_growth(self):
        result = bm.calculate(
            money_current=21500.0, money_prior_year=20000.0, aggregate_name="M2",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            real_gdp_current=25000.0, real_gdp_prior_year=24000.0,
        )
        ratio = next(c for c in result.components if c.key == "money_to_real_output_ratio")
        assert ratio.value == pytest.approx(21500.0 / 25000.0)
        growth_approx = next(c for c in result.components if c.key == "money_to_real_output_growth_approx")
        g_m = (21500.0 / 20000.0 - 1) * 100
        g_y = (25000.0 / 24000.0 - 1) * 100
        assert growth_approx.value == pytest.approx(g_m - g_y)

    @pytest.mark.parametrize(
        "gdp_kwargs",
        [
            {"real_gdp_current": 25000.0},
            {"real_gdp_prior_year": 24000.0},
        ],
    )
    def test_partial_real_gdp_marks_partial_without_type_error(self, gdp_kwargs):
        result = bm.calculate(
            money_current=21500.0, money_prior_year=20000.0, aggregate_name="M2",
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            **gdp_kwargs,
        )
        assert result.coverage == Coverage.PARTIAL
        assert not any(c.key == "money_to_real_output_ratio" for c in result.components)
        assert any("money_to_real_output_ratio unavailable" in w for w in result.warnings)
