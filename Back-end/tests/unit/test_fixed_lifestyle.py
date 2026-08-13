import pytest

from app.engines.country import fixed_lifestyle as fl
from app.engines.shared.errors import DataQualityError
from app.models.enums import Confidence, Coverage

CALCULATED_AT = "2026-08-02T12:00:00Z"

BASE_PRICES = {"rice": 10.0, "steak": 20.0}
BASE_QTY = {"rice": 5.0, "steak": 2.0}


def cfg():
    return fl.FixedLifestyleConfig(basket_version="2026.1")


class TestBasicCalculation:
    def test_yoy_matches_manual_laspeyres(self):
        current = {"rice": 12.0, "steak": 24.0}
        prior_year = {"rice": 11.0, "steak": 22.0}
        result = fl.calculate(
            prices_current=current,
            prices_prior_year=prior_year,
            prices_base=BASE_PRICES,
            quantities_base=BASE_QTY,
            config=cfg(),
            geography="USA",
            period="2026-06",
            calculated_at=CALCULATED_AT,
        )
        fli_t = (12.0 * 5.0 + 24.0 * 2.0) / (10.0 * 5.0 + 20.0 * 2.0) * 100
        fli_t12 = (11.0 * 5.0 + 22.0 * 2.0) / (10.0 * 5.0 + 20.0 * 2.0) * 100
        expected = (fli_t / fli_t12 - 1) * 100
        assert result.value == pytest.approx(expected)
        assert result.coverage == Coverage.FULL

    def test_zero_growth_identical_prices(self):
        result = fl.calculate(
            prices_current=BASE_PRICES, prices_prior_year=BASE_PRICES,
            prices_base=BASE_PRICES, quantities_base=BASE_QTY, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value == pytest.approx(0.0)

    def test_negative_growth_deflation(self):
        current = {"rice": 9.0, "steak": 18.0}
        result = fl.calculate(
            prices_current=current, prices_prior_year=BASE_PRICES,
            prices_base=BASE_PRICES, quantities_base=BASE_QTY, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        assert result.value < 0

    def test_contributions_sum_to_index_minus_100(self):
        current = {"rice": 12.0, "steak": 24.0}
        result = fl.calculate(
            prices_current=current, prices_prior_year=BASE_PRICES,
            prices_base=BASE_PRICES, quantities_base=BASE_QTY, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        fixed_index = next(c for c in result.components if c.key == "fixed_basket_index")
        contributions = [c.value for c in result.components if c.key.startswith("contribution_")]
        assert sum(contributions) == pytest.approx(fixed_index.value - 100, abs=1e-6)


class TestShrinkflation:
    def test_shrinkflation_detected_when_package_shrinks_at_same_price(self):
        current = dict(BASE_PRICES)  # same price
        result = fl.calculate(
            prices_current=current, prices_prior_year=BASE_PRICES,
            prices_base=BASE_PRICES, quantities_base=BASE_QTY, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            package_sizes_current={"rice": 4.0}, package_sizes_base={"rice": 5.0},
        )
        unit_price = next(c for c in result.components if c.key == "unit_price_rice")
        # same price, smaller package -> unit price increased
        assert unit_price.value > 0

    def test_no_shrinkflation_when_package_unchanged(self):
        result = fl.calculate(
            prices_current=BASE_PRICES, prices_prior_year=BASE_PRICES,
            prices_base=BASE_PRICES, quantities_base=BASE_QTY, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            package_sizes_current={"rice": 5.0}, package_sizes_base={"rice": 5.0},
        )
        unit_price = next(c for c in result.components if c.key == "unit_price_rice")
        assert unit_price.value == pytest.approx(0.0)


class TestReplacements:
    def test_replacement_lowers_confidence_and_marks_partial(self):
        result = fl.calculate(
            prices_current=BASE_PRICES, prices_prior_year=BASE_PRICES,
            prices_base=BASE_PRICES, quantities_base=BASE_QTY, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            replacements={"steak": fl.ItemReplacement(item_id="steak", replacement_level="category_proxy")},
        )
        assert result.coverage == Coverage.PARTIAL
        assert result.confidence == Confidence.LOW
        assert result.metadata["quality_confidence"] == "low"
        assert any("substitution" in w for w in result.warnings)

    def test_high_confidence_replacement_keeps_high_confidence(self):
        result = fl.calculate(
            prices_current=BASE_PRICES, prices_prior_year=BASE_PRICES,
            prices_base=BASE_PRICES, quantities_base=BASE_QTY, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            replacements={"steak": fl.ItemReplacement(item_id="steak", replacement_level="identical_product")},
        )
        assert result.confidence == Confidence.HIGH

    def test_no_replacements_full_coverage(self):
        result = fl.calculate(
            prices_current=BASE_PRICES, prices_prior_year=BASE_PRICES,
            prices_base=BASE_PRICES, quantities_base=BASE_QTY, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        rc = next(c for c in result.components if c.key == "replacement_coverage_percent")
        assert rc.value == pytest.approx(100.0)

    def test_invalid_replacement_level_raises(self):
        with pytest.raises(DataQualityError):
            fl.ItemReplacement(item_id="steak", replacement_level="nonsense")


class TestQualityAdjustment:
    def test_no_adjustment_factors_means_views_are_equal(self):
        result = fl.calculate(
            prices_current=BASE_PRICES, prices_prior_year=BASE_PRICES,
            prices_base=BASE_PRICES, quantities_base=BASE_QTY, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
        )
        raw = next(c for c in result.components if c.key == "fixed_basket_index")
        adjusted = next(c for c in result.components if c.key == "fli_quality_adjusted")
        assert raw.value == pytest.approx(adjusted.value)

    def test_explicit_adjusted_prices_change_quality_adjusted_view_only(self):
        result = fl.calculate(
            prices_current=BASE_PRICES, prices_prior_year=BASE_PRICES,
            prices_base=BASE_PRICES, quantities_base=BASE_QTY, config=cfg(),
            geography="USA", period="2026-06", calculated_at=CALCULATED_AT,
            quality_adjusted_prices_current={"rice": 10.0, "steak": 18.0},
        )
        raw = next(c for c in result.components if c.key == "fixed_basket_index")
        adjusted = next(c for c in result.components if c.key == "fli_quality_adjusted")
        assert adjusted.value != pytest.approx(raw.value)


class TestMismatchedBasket:
    def test_missing_current_price_for_basket_item_raises(self):
        with pytest.raises(DataQualityError):
            fl.calculate(
                prices_current={"rice": 12.0},  # missing "steak"
                prices_prior_year=BASE_PRICES,
                prices_base=BASE_PRICES,
                quantities_base=BASE_QTY,
                config=cfg(),
                geography="USA",
                period="2026-06",
                calculated_at=CALCULATED_AT,
            )
