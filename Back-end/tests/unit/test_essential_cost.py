import pytest

from app.engines.country import essential_cost as ec
from app.engines.shared.errors import CoverageThresholdError, MissingRequiredInputError
from app.models.enums import Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"

CATEGORIES = {
    "food": 0.24,
    "housing": 0.42,
    "energy": 0.08,
    "transport": 0.12,
    "healthcare": 0.09,
    "communications": 0.05,
}


def cfg(**overrides):
    defaults = dict(
        version="2026.1",
        methodology="lower_income_expenditure_weights",
        categories=CATEGORIES,
        min_coverage_percent=80.0,
        structurally_dominant_weight=0.20,
    )
    defaults.update(overrides)
    return ec.EssentialBasketConfig(**defaults)


class TestCalculateFromRates:
    def test_full_coverage_matches_manual_formula(self):
        rates = {"food": 5.0, "housing": 6.0, "energy": 10.0, "transport": 3.0, "healthcare": 2.0, "communications": 1.0}
        result = ec.calculate_from_rates(rates, cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT)
        expected = sum(CATEGORIES[k] * rates[k] for k in rates)
        assert result.value == pytest.approx(expected)
        assert result.coverage == Coverage.FULL

    def test_zero_growth_all_categories(self):
        rates = {k: 0.0 for k in CATEGORIES}
        result = ec.calculate_from_rates(rates, cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(0.0)

    def test_negative_growth_deflation(self):
        rates = {k: -2.0 for k in CATEGORIES}
        result = ec.calculate_from_rates(rates, cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT)
        assert result.value == pytest.approx(-2.0)

    def test_extreme_inflation_in_one_category(self):
        rates = {k: 2.0 for k in CATEGORIES}
        rates["energy"] = 900.0
        result = ec.calculate_from_rates(rates, cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT)
        assert result.value > 2.0

    def test_missing_category_renormalizes_and_marks_partial(self):
        rates = {k: 5.0 for k in CATEGORIES if k != "communications"}
        result = ec.calculate_from_rates(rates, cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT)
        assert result.coverage == Coverage.PARTIAL
        assert result.metadata["weights_renormalized"] is True
        assert sum(result.metadata["adjusted_weights"].values()) == pytest.approx(1.0)
        assert "communications" not in result.metadata["adjusted_weights"]
        assert any("renormalized" in w for w in result.warnings)

    def test_missing_category_below_threshold_raises(self):
        rates = {"food": 5.0}  # only 0.24 of 1.0 weight present
        strict_cfg = cfg(min_coverage_percent=90.0)
        with pytest.raises(CoverageThresholdError):
            ec.calculate_from_rates(rates, strict_cfg, geography="USA", period="2026-06", calculated_at=CALCULATED_AT)

    def test_no_matching_categories_raises_missing_input(self):
        with pytest.raises(MissingRequiredInputError):
            ec.calculate_from_rates({"unrelated": 5.0}, cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT)

    def test_component_breakdown_present(self):
        rates = {k: 3.0 for k in CATEGORIES}
        result = ec.calculate_from_rates(rates, cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT)
        assert len(result.components) == len(CATEGORIES)

    def test_original_weights_preserved_alongside_adjusted(self):
        rates = {k: 5.0 for k in CATEGORIES if k != "energy"}
        result = ec.calculate_from_rates(rates, cfg(), geography="USA", period="2026-06", calculated_at=CALCULATED_AT)
        assert result.metadata["original_weights"] == CATEGORIES


class TestEssentialCostIndexPriceLevel:
    def test_matches_laspeyres_formula(self):
        prices_current = {"food": 12.0, "housing": 1200.0}
        prices_base = {"food": 10.0, "housing": 1000.0}
        quantities_base = {"food": 5.0, "housing": 1.0}
        result = ec.essential_cost_index(prices_current, prices_base, quantities_base)
        expected = (12.0 * 5.0 + 1200.0 * 1.0) / (10.0 * 5.0 + 1000.0 * 1.0) * 100
        assert result == pytest.approx(expected)

    def test_calculate_from_price_level_yoy(self):
        result = ec.calculate_from_price_level(
            110.0, 100.0, geography="USA", period="2026-06", calculated_at=CALCULATED_AT
        )
        assert result.value == pytest.approx(10.0)
        assert result.coverage == Coverage.FULL
