"""Indicator 1 -- Headline Consumer Inflation.

COUNTRY_INFLATION_METHODS.md section 4 / CALCULATION_ENGINE_GUIDELINES.md
section 8.1.

Question answered: how much has the average price of the official
household consumption basket changed?
"""

from __future__ import annotations

from app.engines.shared import growth
from app.engines.shared.errors import EngineError
from app.engines.shared.periods import Period, yoy_lag
from app.engines.shared.quality import build_provenance, derive_confidence, gap_warnings
from app.engines.shared.validation import (
    require_lagged_observation,
    require_observation_at,
    validate_unit
)
from app.models.enums import Coverage, Frequency, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.series import ObservationSeries

INDICATOR_ID = "headline_consumer_inflation"
METHODOLOGY_VERSION = "1.0.2"
ACCEPTED_UNITS = (Unit.INDEX,)
ACCEPTED_FREQUENCIES = (Frequency.MONTHLY, Frequency.QUARTERLY, Frequency.ANNUAL)

_THREE_MONTH_HORIZON = 3
_SIX_MONTH_HORIZON = 6


def calculate(
    cpi_series: ObservationSeries,
    period: Period,
    *,
    calculated_at: str,
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """Compute Headline Consumer Inflation for ``period``.

    Required output: year-over-year inflation (the headline ``value``).
    Secondary views (period-over-period, three-month annualized momentum)
    are returned as components; if their required history is missing they
    are reported as unavailable components with a warning rather than
    failing the whole calculation (ENGINE guidelines section 10.1: missing
    data stays missing, it does not block everything that *can* still be
    computed).
    """

    validate_unit_input(cpi_series)
    current = require_observation_at(cpi_series, period, context=INDICATOR_ID)

    lag = yoy_lag(cpi_series.frequency)
    prior_year = require_lagged_observation(cpi_series, period, lag, context=INDICATOR_ID)

    yoy_value = growth.year_over_year(current.value, prior_year.value)

    warnings: list[str] = list(gap_warnings(cpi_series, context=INDICATOR_ID))
    components: list[Component] = []
    used_observations = [current, prior_year]

    # Month-over-month / period-over-period (COUNTRY guidelines section 4.4).
    mom_component, mom_obs = _try_period_over_period(cpi_series, period, warnings)
    components.append(mom_component)
    used_observations.extend(mom_obs)

    # Three- and six-month annualized momentum -- only defined for monthly
    # data. Six-month backs the workbench window rail's "6-month
    # annualised" option alongside the existing three-month figure.
    comps, used_observs, warns = calculate_for_monthly(cpi_series, period)

    if comps:
        components.extend(comps)
    if used_observs:
        used_observations.extend(used_observs)
    if warns:
        warnings.extend(warns)

    confidence = derive_confidence(*used_observations)
    is_estimated = any(o.is_estimated for o in used_observations)

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography=cpi_series.geography,
        period=period.raw,
        value=yoy_value,
        unit=Unit.PERCENT_YOY,
        method="index_year_over_year",
        methodology_version=methodology_version,
        input_series=build_provenance(*used_observations),
        coverage=Coverage.FULL,
        confidence=confidence,
        is_estimated=is_estimated,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=tuple(components),
        config_version=config_version,
        metadata={
            "seasonally_adjusted": current.seasonally_adjusted,
            "basket_update_frequency": None,
            "includes_housing_ownership_costs": None,
        },
    )

def _try_period_over_period(
    series: ObservationSeries, period: Period, warnings: list[str]
) -> tuple[Component, list]:
    key = "mom" if series.frequency == Frequency.MONTHLY else "period_over_period"
    try:
        prior = require_lagged_observation(series, period, 1, context=f"{INDICATOR_ID}.period_over_period")
        current = require_observation_at(series, period, context=INDICATOR_ID)
        value = growth.period_over_period(current.value, prior.value)
        return (
            Component(key=key, label="Period-over-period inflation", value=value, unit=Unit.PERCENT_MOM),
            [prior],
        )
    except EngineError as exc:
        warnings.append(f"period_over_period unavailable: {exc.message}")
        return (
            Component(key=key, label="Period-over-period inflation", value=None, unit=Unit.PERCENT_MOM),
            [],
        )


def _try_three_month_annualized(
    series: ObservationSeries, period: Period, warnings: list[str]
) -> tuple[Component, list]:
    return _try_n_month_annualized(series, period, warnings, horizon=_THREE_MONTH_HORIZON, key="three_month_annualized", label="Three-month annualized momentum")


def _try_n_month_annualized(
    series: ObservationSeries, period: Period, warnings: list[str], *, horizon: int, key: str, label: str
) -> tuple[Component, list]:
    try:
        current = require_observation_at(series, period, context=INDICATOR_ID)
        prior = require_lagged_observation(series, period, horizon, context=f"{INDICATOR_ID}.{key}")
        value = growth.n_period_annualized(current.value, prior.value, n=horizon, periods_per_year=12)
        return (Component(key=key, label=label, value=value, unit=Unit.PERCENT_ANNUALIZED), [prior])
    except EngineError as exc:
        warnings.append(f"{key} unavailable: {exc.message}")
        return (Component(key=key, label=label, value=None, unit=Unit.PERCENT_ANNUALIZED), [])


def validate_unit_input(cpi_series: ObservationSeries, indicator_id: str = INDICATOR_ID):
    validate_unit(cpi_series.unit, ACCEPTED_UNITS, indicator_id=indicator_id)
    if cpi_series.frequency not in ACCEPTED_FREQUENCIES:
        from app.engines.shared.errors import FrequencyMismatchError

        raise FrequencyMismatchError(
            expected="/".join(f.value for f in ACCEPTED_FREQUENCIES),
            received=cpi_series.frequency.value,
            indicator=INDICATOR_ID,
        )

def calculate_for_monthly(
        cpi_series: ObservationSeries,
        period: Period,
) -> tuple[list[Component], list, list[str]]:
    used_observations: list = []
    components: list[Component] = []
    warnings: list[str] = []
    if cpi_series.frequency == Frequency.MONTHLY:
        momentum_component, momentum_obs = _try_three_month_annualized(cpi_series, period, warnings)
        components.append(momentum_component)
        used_observations.extend(momentum_obs)
        six_month_component, six_month_obs = _try_n_month_annualized(
            cpi_series, period, warnings, horizon=_SIX_MONTH_HORIZON, key="six_month_annualized", label="Six-month annualized momentum"
        )
        components.append(six_month_component)
        used_observations.extend(six_month_obs)

    return components, used_observations, warnings