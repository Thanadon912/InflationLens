import pytest

from app.engines.shared.aggregation import (
    chain_linked_index,
    chain_step,
    interquartile_range,
    laspeyres_price_index,
    percentile,
    sample_mean,
    sample_std,
    trimmed_mean,
    unweighted_median,
    weighted_arithmetic_mean,
    weighted_geometric_mean_rates,
    weighted_geometric_price_relative,
    weighted_median,
)
from app.engines.shared.errors import DataQualityError, InvalidWeightError


class TestWeightedArithmeticMean:
    def test_normal(self):
        values = {"a": 2.0, "b": 4.0}
        weights = {"a": 0.5, "b": 0.5}
        assert weighted_arithmetic_mean(values, weights) == pytest.approx(3.0)

    def test_result_within_min_max_of_inputs(self):
        values = {"a": -2.0, "b": 10.0, "c": 3.0}
        weights = {"a": 0.2, "b": 0.3, "c": 0.5}
        result = weighted_arithmetic_mean(values, weights)
        assert min(values.values()) <= result <= max(values.values())

    def test_weights_not_summing_to_one_raises(self):
        with pytest.raises(InvalidWeightError):
            weighted_arithmetic_mean({"a": 1.0, "b": 2.0}, {"a": 0.5, "b": 0.6})

    def test_negative_weight_raises(self):
        with pytest.raises(InvalidWeightError):
            weighted_arithmetic_mean({"a": 1.0, "b": 2.0}, {"a": 1.5, "b": -0.5})

    def test_mismatched_keys_raises(self):
        with pytest.raises(InvalidWeightError):
            weighted_arithmetic_mean({"a": 1.0}, {"b": 1.0})

    def test_empty_raises(self):
        with pytest.raises(InvalidWeightError):
            weighted_arithmetic_mean({}, {})

    def test_zero_values(self):
        assert weighted_arithmetic_mean({"a": 0.0, "b": 0.0}, {"a": 0.4, "b": 0.6}) == pytest.approx(0.0)

    def test_negative_values_deflation_case(self):
        result = weighted_arithmetic_mean({"a": -2.0, "b": -4.0}, {"a": 0.5, "b": 0.5})
        assert result == pytest.approx(-3.0)


class TestWeightedGeometricMeanRates:
    def test_normal(self):
        rates = {"a": 10.0, "b": 0.0}
        weights = {"a": 0.5, "b": 0.5}
        result = weighted_geometric_mean_rates(rates, weights)
        expected = ((1.10**0.5) * (1.00**0.5) - 1) * 100
        assert result == pytest.approx(expected)

    def test_zero_growth_all_components(self):
        result = weighted_geometric_mean_rates({"a": 0.0, "b": 0.0}, {"a": 0.5, "b": 0.5})
        assert result == pytest.approx(0.0)

    def test_extreme_inflation_component(self):
        result = weighted_geometric_mean_rates({"a": 900.0, "b": 0.0}, {"a": 0.5, "b": 0.5})
        assert result > 0

    def test_deflation_component(self):
        result = weighted_geometric_mean_rates({"a": -5.0, "b": -5.0}, {"a": 0.5, "b": 0.5})
        assert result == pytest.approx(-5.0)

    def test_rate_at_negative_100_percent_raises(self):
        with pytest.raises(DataQualityError):
            weighted_geometric_mean_rates({"a": -100.0}, {"a": 1.0})

    def test_rate_below_negative_100_percent_raises(self):
        with pytest.raises(DataQualityError):
            weighted_geometric_mean_rates({"a": -150.0}, {"a": 1.0})

    def test_weights_not_summing_to_one_raises(self):
        with pytest.raises(InvalidWeightError):
            weighted_geometric_mean_rates({"a": 1.0, "b": 2.0}, {"a": 0.2, "b": 0.2})


class TestWeightedGeometricPriceRelative:
    def test_normal(self):
        relatives = {"a": 1.05, "b": 1.10}
        weights = {"a": 0.5, "b": 0.5}
        result = weighted_geometric_price_relative(relatives, weights)
        expected = (1.05**0.5) * (1.10**0.5)
        assert result == pytest.approx(expected)

    def test_identical_prices_relative_one_is_neutral(self):
        result = weighted_geometric_price_relative({"a": 1.0, "b": 1.0}, {"a": 0.3, "b": 0.7})
        assert result == pytest.approx(1.0)

    def test_non_positive_relative_raises(self):
        with pytest.raises(DataQualityError):
            weighted_geometric_price_relative({"a": 0.0}, {"a": 1.0})
        with pytest.raises(DataQualityError):
            weighted_geometric_price_relative({"a": -1.0}, {"a": 1.0})


class TestWeightedMedian:
    def test_single_dominant_weight(self):
        values = {"a": 1.0, "b": 2.0, "c": 3.0}
        weights = {"a": 0.6, "b": 0.2, "c": 0.2}
        assert weighted_median(values, weights) == pytest.approx(1.0)

    def test_matches_cumulative_definition(self):
        values = {"a": 1.0, "b": 5.0, "c": 9.0}
        weights = {"a": 0.3, "b": 0.3, "c": 0.4}
        # cumulative: a=0.3 (<0.5), a+b=0.6 (>=0.5) -> median is b's value
        assert weighted_median(values, weights) == pytest.approx(5.0)

    def test_order_invariance(self):
        values_1 = {"a": 1.0, "b": 5.0, "c": 9.0}
        weights_1 = {"a": 0.3, "b": 0.3, "c": 0.4}
        values_2 = {"c": 9.0, "a": 1.0, "b": 5.0}
        weights_2 = {"c": 0.4, "b": 0.3, "a": 0.3}
        assert weighted_median(values_1, weights_1) == weighted_median(values_2, weights_2)

    def test_equal_weights_reduces_to_middle_ish_value(self):
        values = {"a": 1.0, "b": 2.0, "c": 3.0}
        weights = {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}
        assert weighted_median(values, weights) == pytest.approx(2.0)


class TestUnweightedMedian:
    def test_odd_count(self):
        assert unweighted_median([3.0, 1.0, 2.0]) == pytest.approx(2.0)

    def test_even_count_averages_middle_two(self):
        assert unweighted_median([1.0, 2.0, 3.0, 4.0]) == pytest.approx(2.5)

    def test_order_invariance(self):
        assert unweighted_median([5.0, 1.0, 3.0, 2.0]) == unweighted_median([1.0, 2.0, 3.0, 5.0])

    def test_single_value(self):
        assert unweighted_median([7.0]) == pytest.approx(7.0)

    def test_empty_raises(self):
        with pytest.raises(DataQualityError):
            unweighted_median([])

    def test_does_not_remove_hyperinflation_outlier(self):
        # GLOBAL guidelines section 6.4/14.3: hyperinflation observations
        # must remain visible; median is a robustness view, not a filter.
        values = [2.0, 3.0, 4.0, 5.0, 50000.0]
        assert unweighted_median(values) == pytest.approx(4.0)


class TestPercentileAndIqr:
    def test_p50_matches_median_for_odd_count(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        assert percentile(values, 50) == pytest.approx(unweighted_median(values))

    def test_p0_is_min_p100_is_max(self):
        values = [3.0, 1.0, 4.0, 1.5, 9.0]
        assert percentile(values, 0) == pytest.approx(min(values))
        assert percentile(values, 100) == pytest.approx(max(values))

    def test_single_value(self):
        assert percentile([5.0], 25) == pytest.approx(5.0)

    def test_interquartile_range(self):
        values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        iqr = interquartile_range(values)
        assert iqr == pytest.approx(percentile(values, 75) - percentile(values, 25))
        assert iqr >= 0

    def test_out_of_range_p_raises(self):
        with pytest.raises(DataQualityError):
            percentile([1.0, 2.0], 150)

    def test_empty_raises(self):
        with pytest.raises(DataQualityError):
            percentile([], 50)


class TestSampleMeanStd:
    def test_mean(self):
        assert sample_mean([2.0, 4.0, 6.0]) == pytest.approx(4.0)

    def test_std_matches_manual_bessel_corrected_formula(self):
        values = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        mean = sum(values) / len(values)
        expected = (sum((x - mean) ** 2 for x in values) / (len(values) - 1)) ** 0.5
        assert sample_std(values) == pytest.approx(expected)

    def test_zero_dispersion_identical_values(self):
        assert sample_std([3.0, 3.0, 3.0]) == pytest.approx(0.0)

    def test_single_value_raises(self):
        with pytest.raises(DataQualityError):
            sample_std([1.0])

    def test_empty_mean_raises(self):
        with pytest.raises(DataQualityError):
            sample_mean([])


class TestTrimmedMean:
    def test_normal_excludes_extremes(self):
        values = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0, "e": 100.0}
        weights = {"a": 0.2, "b": 0.2, "c": 0.2, "d": 0.2, "e": 0.2}
        result, retained = trimmed_mean(values, weights, alpha=0.2, beta=0.2)
        assert "a" not in retained
        assert "e" not in retained
        assert result == pytest.approx(3.0)  # mean of b,c,d = 3.0

    def test_zero_trim_equals_full_weighted_mean(self):
        values = {"a": 1.0, "b": 2.0, "c": 3.0}
        weights = {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}
        result, retained = trimmed_mean(values, weights, alpha=0.0, beta=0.0)
        assert set(retained) == {"a", "b", "c"}
        assert result == pytest.approx(2.0)

    def test_clip_boundary_handling_includes_partial_weight(self):
        values = {"a": 1.0, "b": 2.0, "c": 3.0, "d": 4.0}
        weights = {"a": 0.25, "b": 0.25, "c": 0.25, "d": 0.25}
        result, retained = trimmed_mean(
            values, weights, alpha=0.1, beta=0.1, boundary_handling="clip"
        )
        assert "a" in retained  # partially retained (clip includes edge components)
        assert result == pytest.approx((2.0 + 3.0) / 2, abs=0.3)

    def test_invalid_alpha_beta_raises(self):
        with pytest.raises(DataQualityError):
            trimmed_mean({"a": 1.0}, {"a": 1.0}, alpha=0.6, beta=0.6)

    def test_unsupported_boundary_handling_raises(self):
        with pytest.raises(DataQualityError):
            trimmed_mean(
                {"a": 1.0, "b": 2.0},
                {"a": 0.5, "b": 0.5},
                alpha=0.0,
                beta=0.0,
                boundary_handling="nonsense",
            )

    def test_weight_mismatch_raises(self):
        with pytest.raises(InvalidWeightError):
            trimmed_mean({"a": 1.0}, {"b": 1.0}, alpha=0.0, beta=0.0)


class TestLaspeyresPriceIndex:
    def test_no_price_change_gives_index_100(self):
        prices = {"a": 2.0, "b": 5.0}
        result = laspeyres_price_index(prices, prices, {"a": 10.0, "b": 4.0})
        assert result == pytest.approx(100.0)

    def test_uniform_price_increase_scales_index(self):
        base_prices = {"a": 2.0, "b": 5.0}
        current_prices = {"a": 2.2, "b": 5.5}  # +10% uniformly
        result = laspeyres_price_index(current_prices, base_prices, {"a": 10.0, "b": 4.0})
        assert result == pytest.approx(110.0)

    def test_matches_manual_computation(self):
        current = {"a": 3.0, "b": 6.0}
        base = {"a": 2.0, "b": 5.0}
        qty = {"a": 10.0, "b": 4.0}
        result = laspeyres_price_index(current, base, qty)
        expected = (3.0 * 10.0 + 6.0 * 4.0) / (2.0 * 10.0 + 5.0 * 4.0) * 100
        assert result == pytest.approx(expected)

    def test_mismatched_keys_raises(self):
        with pytest.raises(DataQualityError):
            laspeyres_price_index({"a": 1.0}, {"a": 1.0, "b": 2.0}, {"a": 1.0, "b": 2.0})

    def test_zero_base_value_raises(self):
        with pytest.raises(DataQualityError):
            laspeyres_price_index({"a": 1.0}, {"a": 0.0}, {"a": 5.0})


class TestChainLinkedIndex:
    def test_base_is_100_by_default(self):
        levels = chain_linked_index([1.02, 1.01])
        assert levels[0] == pytest.approx(100.0)

    def test_step_by_step_matches_batch(self):
        relatives = [1.02, 0.99, 1.01]
        levels = chain_linked_index(relatives, base=100.0)
        manual = 100.0
        for r in relatives:
            manual = chain_step(manual, r)
        assert levels[-1] == pytest.approx(manual)

    def test_no_growth_keeps_index_flat(self):
        levels = chain_linked_index([1.0, 1.0, 1.0])
        assert all(level == pytest.approx(100.0) for level in levels)

    def test_non_positive_relative_raises(self):
        with pytest.raises(DataQualityError):
            chain_step(100.0, 0.0)
        with pytest.raises(DataQualityError):
            chain_step(100.0, -0.5)
