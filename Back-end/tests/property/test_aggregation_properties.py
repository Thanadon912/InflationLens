"""Property tests for aggregation formulas (ENGINE guidelines section 15.2):

- weighted means must stay within the minimum and maximum input values
  when weights are valid;
- a median must not depend on country order;
- renormalized weights must sum to one;
- multiplying all basket quantities by the same constant should not
  change a price index (tested here via the geometric price relative).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from app.engines.shared.aggregation import (
    unweighted_median,
    weighted_arithmetic_mean,
    weighted_geometric_price_relative,
    weighted_median,
)
from app.engines.shared.coverage import renormalize_weights

finite_values = st.floats(min_value=-1e6, max_value=1e6, allow_nan=False, allow_infinity=False)
positive_values = st.floats(min_value=1e-6, max_value=1e6, allow_nan=False, allow_infinity=False)


def _weighted_case(n):
    """A strategy for (values_dict, weights_dict) with n components and
    weights that sum to exactly 1."""

    keys = [f"k{i}" for i in range(n)]

    @st.composite
    def _inner(draw):
        values = {k: draw(finite_values) for k in keys}
        raw_weights = [draw(st.floats(min_value=0.0, max_value=1.0)) for _ in keys]
        total = sum(raw_weights)
        if total == 0:
            raw_weights = [1.0] * n
            total = float(n)
        weights = {k: w / total for k, w in zip(keys, raw_weights)}
        return values, weights

    return _inner()


@given(_weighted_case(4))
def test_weighted_arithmetic_mean_within_min_max(case):
    values, weights = case
    result = weighted_arithmetic_mean(values, weights)
    assert min(values.values()) - 1e-9 <= result <= max(values.values()) + 1e-9


@given(_weighted_case(5))
def test_weighted_median_within_min_max(case):
    values, weights = case
    result = weighted_median(values, weights)
    assert min(values.values()) - 1e-9 <= result <= max(values.values()) + 1e-9


@given(st.lists(finite_values, min_size=1, max_size=15))
def test_unweighted_median_order_invariant(values):
    import random

    shuffled = values[:]
    random.Random(42).shuffle(shuffled)
    assert unweighted_median(values) == pytest.approx(unweighted_median(shuffled))


@given(_weighted_case(4))
def test_weighted_median_order_invariant(case):
    values, weights = case
    keys = list(values.keys())
    reordered_values = {k: values[k] for k in reversed(keys)}
    reordered_weights = {k: weights[k] for k in reversed(keys)}
    assert weighted_median(values, weights) == pytest.approx(
        weighted_median(reordered_values, reordered_weights)
    )


@given(
    relatives=st.dictionaries(
        st.sampled_from(["a", "b", "c"]), positive_values, min_size=3, max_size=3
    ),
    scale=st.floats(min_value=0.1, max_value=10.0),
)
def test_scaling_all_price_relatives_by_constant_scales_the_index(relatives, scale):
    # Multiplying every price relative by the same constant is analogous
    # to multiplying all basket quantities by the same constant: the
    # geometric aggregate scales by exactly that constant (since weights
    # sum to 1, prod(scale * r_i)^w_i = scale * prod(r_i)^w_i).
    weights = {"a": 0.2, "b": 0.3, "c": 0.5}
    original = weighted_geometric_price_relative(relatives, weights)
    scaled_relatives = {k: v * scale for k, v in relatives.items()}
    scaled = weighted_geometric_price_relative(scaled_relatives, weights)
    assert scaled == pytest.approx(original * scale, rel=1e-6)


@given(
    weights=st.dictionaries(
        st.sampled_from(["a", "b", "c", "d"]),
        st.floats(min_value=0.01, max_value=1.0),
        min_size=2,
        max_size=4,
    )
)
def test_renormalized_weights_sum_to_one(weights):
    available = list(weights.keys())[: max(1, len(weights) - 1)]
    result = renormalize_weights(weights, available)
    assert sum(result.values()) == pytest.approx(1.0, abs=1e-9)
