"""Global Indicator 1 -- Global Consumer Inflation.

GLOBAL_INFLATION_METHODS.md section 5 / CALCULATION_ENGINE_GUIDELINES.md
section 9.1.

Question answered: how quickly are consumer prices rising across the
global household-consumption system? Not a literal global household
basket -- each country's CPI basket remains local (GLOBAL guidelines
section 5.6).
"""

from __future__ import annotations

from collections.abc import Mapping

from app.engines.shared.aggregation import (
    chain_step,
    weighted_arithmetic_mean,
    weighted_geometric_price_relative,
)
from app.engines.shared.coverage import align_weights_to_values, build_coverage_report
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance

INDICATOR_ID = "global_consumer_inflation"
METHODOLOGY_VERSION = "1.0.2"
DEFAULT_WEIGHT_METHOD = "household_consumption_ppp"


def calculate(
    *,
    country_headline_rates: Mapping[str, float],
    country_weights: Mapping[str, float],
    all_geographies: tuple[str, ...],
    period: str,
    calculated_at: str,
    weight_method: str = DEFAULT_WEIGHT_METHOD,
    country_price_relatives: Mapping[str, float] | None = None,
    global_index_previous_period: float | None = None,
    global_index_prior_year: float | None = None,
    population_by_geo: Mapping[str, float] | None = None,
    gdp_ppp_by_geo: Mapping[str, float] | None = None,
    consumption_ppp_by_geo: Mapping[str, float] | None = None,
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """pi^GCI_t = sum_c w^consPPP_{c,t-1} pi^headline_{c,t} (GLOBAL
    guidelines section 5.3), the arithmetic default form. ``country_weights``
    must already be lagged (w_{c,t-1}) per GLOBAL guidelines section 4.6.

    ``country_price_relatives`` (P_{c,t}/P_{c,t-1} per country), if
    supplied, additionally computes the geometric period-relative
    aggregation from section 5.4 as a secondary component. This engine is
    stateless and does not persist a running chain index across calls
    (GLOBAL_INFLATION_METHODS.md section 3.4's ``GPI_t = GPI_{t-1} *
    R^G_t`` chaining is available to callers via
    ``app.engines.shared.aggregation.chain_step``/``chain_linked_index``
    using this period's relative as one link).
    """

    aligned_weights = align_weights_to_values(
        country_headline_rates, country_weights, context=f"{INDICATOR_ID}.country_weights"
    )
    arithmetic_rate = weighted_arithmetic_mean(country_headline_rates, aligned_weights)

    components: list[Component] = []
    if country_price_relatives:
        rel_weights = align_weights_to_values(
            country_price_relatives, country_weights, context=f"{INDICATOR_ID}.country_price_relatives"
        )
        geometric_relative = weighted_geometric_price_relative(country_price_relatives, rel_weights)
        components.append(
            Component(
                key="geometric_period_relative_percent",
                label="Geometric Global Period Inflation",
                value=(geometric_relative - 1) * 100,
                unit=Unit.PERCENT_MOM,
            )
        )
        if global_index_previous_period is not None:
            global_index = chain_step(global_index_previous_period, geometric_relative)
            components.append(Component(key="geometric_global_index", label="Geometric Chain-Linked Global CPI", value=global_index, unit=Unit.INDEX))
            if global_index_prior_year is not None:
                from app.engines.shared.growth import year_over_year
                components.append(Component(key="geometric_yoy", label="Geometric Global Consumer Inflation (YoY)", value=year_over_year(global_index, global_index_prior_year), unit=Unit.PERCENT_YOY))

    coverage_report = build_coverage_report(
        all_geographies=all_geographies,
        included_geographies=country_headline_rates.keys(),
        population_by_geo=population_by_geo,
        gdp_ppp_by_geo=gdp_ppp_by_geo,
        consumption_ppp_by_geo=consumption_ppp_by_geo,
    )

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography="GLOBAL",
        period=period,
        value=arithmetic_rate,
        unit=Unit.PERCENT_YOY,
        method="consumption_ppp_weighted_arithmetic_mean",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.FULL if not coverage_report.missing_geographies else Coverage.PARTIAL,
        confidence=Confidence.HIGH,
        is_estimated=False,
        warnings=(),
        calculated_at=calculated_at,
        components=tuple(components),
        coverage_report=coverage_report,
        config_version=config_version,
        metadata={"weight_method": weight_method},
    )
