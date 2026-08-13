import math

import pytest

from app.engines.shared.errors import DataQualityError
from app.engines.shared.growth import (
    annualized,
    log_change,
    n_period_annualized,
    period_over_period,
    real_growth,
    real_growth_approx,
    year_over_year,
)


class TestYearOverYear:
    def test_normal_growth(self):
        # CPI 321.5 vs 311.5 a year earlier -> positive growth
        result = year_over_year(321.5, 311.5)
        assert result == pytest.approx((321.5 / 311.5 - 1) * 100)

    def test_zero_growth_identical_values(self):
        assert year_over_year(100.0, 100.0) == pytest.approx(0.0)

    def test_negative_growth_deflation(self):
        result = year_over_year(95.0, 100.0)
        assert result < 0
        assert result == pytest.approx(-5.0)

    def test_extreme_inflation(self):
        # hyperinflation: index 100x higher than a year ago
        result = year_over_year(10000.0, 100.0)
        assert result == pytest.approx(9900.0)

    def test_zero_denominator_raises(self):
        with pytest.raises(DataQualityError):
            year_over_year(100.0, 0.0)

    def test_negative_index_denominator_raises_on_non_finite_only(self):
        # negative denominator is not itself forbidden by this pure
        # function (index positivity is a validation-layer concern), but
        # it must not silently succeed with a nonsensical division by an
        # impossible level; zero must still raise.
        with pytest.raises(DataQualityError):
            year_over_year(100.0, 0.0)

    def test_non_finite_denominator_raises(self):
        with pytest.raises(DataQualityError):
            year_over_year(100.0, math.nan)

    def test_negative_index_current_allowed_math(self):
        # growth math itself does not forbid a negative current value;
        # index positivity is enforced separately by validation.py
        result = year_over_year(-10.0, 100.0)
        assert result == pytest.approx(-110.0)


class TestPeriodOverPeriod:
    def test_normal(self):
        assert period_over_period(102.0, 100.0) == pytest.approx(2.0)

    def test_zero_growth(self):
        assert period_over_period(100.0, 100.0) == pytest.approx(0.0)

    def test_negative_growth(self):
        assert period_over_period(98.0, 100.0) == pytest.approx(-2.0)

    def test_zero_denominator_raises(self):
        with pytest.raises(DataQualityError):
            period_over_period(100.0, 0.0)


class TestAnnualized:
    def test_monthly_annualization_matches_manual_formula(self):
        # 0.5% MoM annualized over 12 months
        result = annualized(100.5, 100.0, 12)
        expected = ((100.5 / 100.0) ** 12 - 1) * 100
        assert result == pytest.approx(expected)

    def test_zero_growth(self):
        assert annualized(100.0, 100.0, 12) == pytest.approx(0.0)

    def test_negative_growth_deflation(self):
        result = annualized(99.5, 100.0, 12)
        assert result < 0

    def test_zero_denominator_raises(self):
        with pytest.raises(DataQualityError):
            annualized(100.0, 0.0, 12)

    def test_negative_ratio_raises(self):
        with pytest.raises(DataQualityError):
            annualized(-100.0, 100.0, 12)


class TestNPeriodAnnualized:
    def test_three_month_annualized_matches_documented_formula(self):
        # COUNTRY guidelines section 4.4: [(CPI_t/CPI_{t-3})^4 - 1] x 100
        cpi_t, cpi_t3 = 321.5, 315.0
        result = n_period_annualized(cpi_t, cpi_t3, n=3, periods_per_year=12)
        expected = ((cpi_t / cpi_t3) ** 4 - 1) * 100
        assert result == pytest.approx(expected)

    def test_n_equal_to_periods_per_year_reduces_to_yoy_style_exponent_one(self):
        # exponent = periods_per_year / n = 1 when n == periods_per_year
        result = n_period_annualized(110.0, 100.0, n=12, periods_per_year=12)
        assert result == pytest.approx(10.0)

    def test_zero_n_raises(self):
        with pytest.raises(DataQualityError):
            n_period_annualized(100.0, 100.0, n=0, periods_per_year=12)

    def test_zero_denominator_raises(self):
        with pytest.raises(DataQualityError):
            n_period_annualized(100.0, 0.0, n=3, periods_per_year=12)


class TestRealGrowth:
    def test_matches_documented_exact_formula(self):
        nominal, inflation = 5.0, 3.0
        result = real_growth(nominal, inflation)
        expected = ((1 + nominal / 100) / (1 + inflation / 100) - 1) * 100
        assert result == pytest.approx(expected)

    def test_zero_inflation_real_equals_nominal(self):
        assert real_growth(4.0, 0.0) == pytest.approx(4.0)

    def test_negative_real_growth_when_inflation_exceeds_nominal(self):
        result = real_growth(2.0, 5.0)
        assert result < 0

    def test_extreme_deflation_boundary_raises(self):
        # inflation = -100% makes the denominator zero
        with pytest.raises(DataQualityError):
            real_growth(2.0, -100.0)

    def test_approx_matches_subtraction(self):
        assert real_growth_approx(5.0, 3.0) == pytest.approx(2.0)

    def test_approx_and_exact_are_close_for_small_rates(self):
        exact = real_growth(2.0, 1.5)
        approx = real_growth_approx(2.0, 1.5)
        assert exact == pytest.approx(approx, abs=0.02)


class TestLogChange:
    def test_matches_documented_formula(self):
        x_t, x_tk = 321.5, 311.5
        result = log_change(x_t, x_tk)
        expected = 100 * (math.log(x_t) - math.log(x_tk))
        assert result == pytest.approx(expected)

    def test_zero_change(self):
        assert log_change(100.0, 100.0) == pytest.approx(0.0)

    def test_approximates_percent_growth_for_small_changes(self):
        # doc: 100 * ln(X_t) ~= g_t(X) for small changes
        yoy = year_over_year(101.0, 100.0)
        log_approx = log_change(101.0, 100.0)
        assert yoy == pytest.approx(log_approx, abs=0.01)

    def test_non_positive_values_raise(self):
        with pytest.raises(DataQualityError):
            log_change(0.0, 100.0)
        with pytest.raises(DataQualityError):
            log_change(100.0, -1.0)
