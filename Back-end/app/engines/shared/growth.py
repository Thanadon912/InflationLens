"""Pure growth-rate formulas.

Every function here is a direct, literal translation of a formula in
CALCULATION_ENGINE_GUIDELINES.md section 7 (mirrored in
COUNTRY_INFLATION_METHODS.md section 3 and GLOBAL_INFLATION_METHODS.md
section 3). They take plain numbers and return plain numbers — no
observation objects, no configuration, no I/O — so each formula can be
tested in complete isolation and reused by every engine module that needs
it.

None of these functions round their result. ENGINE guidelines section 16.3
is explicit: "Do not round intermediate calculations. Round only at the
presentation layer." Rounding happens only in the API serialization layer.
"""

from __future__ import annotations

import math

from app.engines.shared.errors import DataQualityError


def _check_denominator(value: float, *, context: str) -> None:
    if value == 0:
        raise DataQualityError(f"Zero denominator in {context}", context=context, value=value)
    if not math.isfinite(value):
        raise DataQualityError(f"Non-finite denominator in {context}", context=context, value=value)


def year_over_year(x_t: float, x_t_minus_k: float) -> float:
    """g^YoY_t = (X_t / X_{t-k} - 1) x 100.

    ENGINE guidelines section 7.1 / COUNTRY section 3.1. ``k`` is chosen by
    the caller via ``app.engines.shared.periods.yoy_lag`` before looking up
    ``x_t_minus_k``; this function only needs the two values.
    """

    _check_denominator(x_t_minus_k, context="year_over_year")
    return (x_t / x_t_minus_k - 1) * 100


def period_over_period(x_t: float, x_t_minus_1: float) -> float:
    """g_t = (X_t / X_{t-1} - 1) x 100 (ENGINE guidelines section 7.2)."""

    _check_denominator(x_t_minus_1, context="period_over_period")
    return (x_t / x_t_minus_1 - 1) * 100


def annualized(x_t: float, x_t_minus_1: float, periods_per_year: int) -> float:
    """g^Ann_t = [(X_t / X_{t-1})^m - 1] x 100 (ENGINE guidelines section 7.3).

    ``periods_per_year`` (m) is 12 for monthly data, 4 for quarterly data.
    """

    _check_denominator(x_t_minus_1, context="annualized")
    ratio = x_t / x_t_minus_1
    if ratio < 0:
        raise DataQualityError(
            "Cannot annualize a negative period-over-period ratio",
            context="annualized",
            ratio=ratio,
        )
    return (ratio**periods_per_year - 1) * 100


def n_period_annualized(x_t: float, x_t_minus_n: float, n: int, periods_per_year: int) -> float:
    """Annualized growth over an n-period horizon.

    Generalizes COUNTRY_INFLATION_METHODS.md section 4.4's three-month
    annualized momentum, ``[(CPI_t / CPI_{t-3})^4 - 1] x 100``, to an
    arbitrary horizon ``n`` (in native periods) at a given
    ``periods_per_year``. With n=3 and periods_per_year=12, the exponent
    ``periods_per_year / n`` is 4, reproducing the documented formula
    exactly.
    """

    if n <= 0:
        raise DataQualityError("n_period_annualized requires n > 0", context="n_period_annualized", n=n)
    _check_denominator(x_t_minus_n, context="n_period_annualized")
    ratio = x_t / x_t_minus_n
    if ratio < 0:
        raise DataQualityError(
            "Cannot annualize a negative n-period ratio",
            context="n_period_annualized",
            ratio=ratio,
        )
    exponent = periods_per_year / n
    return (ratio**exponent - 1) * 100


def real_growth(nominal_growth_percent: float, inflation_percent: float) -> float:
    """g^real = [(1 + g^nominal) / (1 + pi) - 1] x 100 (ENGINE guidelines
    section 7.4 / COUNTRY section 13.2).

    Inputs and output are all in percent (e.g. ``3.2`` means 3.2%); the
    decimal conversion required "inside the fraction" by the docs happens
    internally.
    """

    denominator = 1 + inflation_percent / 100
    _check_denominator(denominator, context="real_growth")
    return ((1 + nominal_growth_percent / 100) / denominator - 1) * 100


def real_growth_approx(nominal_growth_percent: float, inflation_percent: float) -> float:
    """g^realwage ~= g^nominalwage - pi (COUNTRY guidelines section 13.2,
    the documented linear approximation to :func:`real_growth`)."""

    return nominal_growth_percent - inflation_percent


def log_change(x_t: float, x_t_minus_k: float) -> float:
    """100 x [ln(X_t) - ln(X_{t-k})] (COUNTRY guidelines section 3.7),
    the log-change approximation to year-over-year growth for small
    changes."""

    if x_t <= 0 or x_t_minus_k <= 0:
        raise DataQualityError(
            "log_change requires strictly positive values",
            context="log_change",
            x_t=x_t,
            x_t_minus_k=x_t_minus_k,
        )
    return 100 * (math.log(x_t) - math.log(x_t_minus_k))
