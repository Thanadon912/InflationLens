"""Property tests for growth formulas.

CALCULATION_ENGINE_GUIDELINES.md section 15.2 requires (among others):
"identical prices should produce zero inflation." This module encodes
that and related invariants as Hypothesis property tests so they are
checked against hundreds of generated inputs rather than a handful of
examples.
"""

from __future__ import annotations

import math

import pytest
from hypothesis import assume, given
from hypothesis import strategies as st

from app.engines.shared.errors import DataQualityError
from app.engines.shared.growth import (
    annualized,
    log_change,
    period_over_period,
    year_over_year,
)

positive_values = st.floats(
    min_value=1e-6, max_value=1e9, allow_nan=False, allow_infinity=False
)

# The complement of positive_values: exactly the denominators
# _check_denominator (app/engines/shared/growth.py) exists to reject. The
# strategies above deliberately exclude these; without dedicated coverage
# the guards they exercise would never be property-tested at all.
non_finite_values = st.sampled_from([math.inf, -math.inf, math.nan])


@given(x=positive_values)
def test_yoy_of_identical_value_is_zero(x):
    assert year_over_year(x, x) == pytest_approx_zero()


@given(x=positive_values)
def test_pop_of_identical_value_is_zero(x):
    assert period_over_period(x, x) == pytest_approx_zero()


@given(x=positive_values)
def test_annualized_of_identical_value_is_zero(x):
    assert annualized(x, x, 12) == pytest_approx_zero()


@given(x=positive_values)
def test_log_change_of_identical_value_is_zero(x):
    assert log_change(x, x) == pytest_approx_zero()


@given(x_t=positive_values, x_prev=positive_values)
def test_yoy_sign_matches_direction_of_change(x_t, x_prev):
    result = year_over_year(x_t, x_prev)
    if x_t > x_prev:
        assert result > 0
    elif x_t < x_prev:
        assert result < 0
    else:
        assert result == pytest_approx_zero()


@given(x_t=positive_values, x_prev=positive_values, k=st.integers(min_value=1, max_value=100))
def test_scaling_both_values_by_same_constant_does_not_change_growth(x_t, x_prev, k):
    # Scaling numerator and denominator by the same positive constant must
    # not change a ratio-based growth rate. This mirrors the documented
    # invariant "multiplying all basket quantities by the same constant
    # should not change a price index" applied to the growth formula.
    scale = 3.7
    original = year_over_year(x_t, x_prev)
    scaled = year_over_year(x_t * scale, x_prev * scale)
    assert scaled == pytest_approx(original)


@given(
    x_prev=positive_values,
    small_relative_change=st.floats(min_value=-0.01, max_value=0.01, allow_nan=False),
)
def test_yoy_and_log_change_agree_for_small_moves(x_prev, small_relative_change):
    # 100 * ln(X_t/X_{t-k}) approximates g_t(X) for small changes
    # (COUNTRY guidelines section 3.7). Construct x_t directly as a small
    # perturbation of x_prev instead of generating two independent values
    # and filtering, which Hypothesis flags as excessive filtering.
    x_t = x_prev * (1 + small_relative_change)
    assume(x_t > 0)
    yoy = year_over_year(x_t, x_prev)
    log_approx = log_change(x_t, x_prev)
    assert math.isclose(yoy, log_approx, abs_tol=0.05)


@given(x_t=positive_values)
def test_yoy_zero_denominator_always_raises(x_t):
    with pytest.raises(DataQualityError):
        year_over_year(x_t, 0.0)


@given(x_t=positive_values, x_t_minus_k=non_finite_values)
def test_yoy_non_finite_denominator_always_raises(x_t, x_t_minus_k):
    with pytest.raises(DataQualityError):
        year_over_year(x_t, x_t_minus_k)


@given(x_t=positive_values)
def test_period_over_period_zero_denominator_always_raises(x_t):
    with pytest.raises(DataQualityError):
        period_over_period(x_t, 0.0)


@given(x_t=positive_values, x_t_1=non_finite_values)
def test_annualized_non_finite_denominator_always_raises(x_t, x_t_1):
    with pytest.raises(DataQualityError):
        annualized(x_t, x_t_1, 12)


def pytest_approx_zero():
    from pytest import approx

    return approx(0.0, abs=1e-8)


def pytest_approx(value):
    from pytest import approx

    return approx(value, rel=1e-6, abs=1e-8)
