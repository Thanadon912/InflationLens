"""Global Indicator 3 -- Global Essential Inflation.

GLOBAL_INFLATION_METHODS.md section 7 / CALCULATION_ENGINE_GUIDELINES.md
section 9.3.

Question answered: how quickly are globally essential household costs
rising? GLOBAL guidelines section 7.2 requires each country's essential
inflation to be calculated first (see
``app.engines.country.essential_cost``) before this module aggregates
across countries.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.engines.shared.aggregation import weighted_arithmetic_mean
from app.engines.shared.coverage import build_coverage_report
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance

INDICATOR_ID = "global_essential_inflation"
METHODOLOGY_VERSION = "1.0.1"


def calculate(
    *,
    country_essential_rates: Mapping[str, float],
    consumption_ppp_weights: Mapping[str, float],
    all_geographies: tuple[str, ...],
    period: str,
    calculated_at: str,
    population_weights: Mapping[str, float] | None = None,
    population_by_geo: Mapping[str, float] | None = None,
    gdp_ppp_by_geo: Mapping[str, float] | None = None,
    consumption_ppp_by_geo: Mapping[str, float] | None = None,
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """pi^GEI_t = sum_c w^consPPP_{c,t-1} pi^essential_{c,t} (GLOBAL
    guidelines section 7.3), the consumption-PPP-weighted default. The
    population-weighted alternative (section 7.4) is reported as a
    component when ``population_weights`` is supplied.
    """

    consumption_weighted = weighted_arithmetic_mean(country_essential_rates, consumption_ppp_weights)

    components = []
    if population_weights:
        pop_weighted = weighted_arithmetic_mean(country_essential_rates, population_weights)
        components.append(
            Component(
                key="population_weighted",
                label="Population-Weighted Global Essential Inflation",
                value=pop_weighted,
                unit=Unit.PERCENT_YOY,
            )
        )

    coverage_report = build_coverage_report(
        all_geographies=all_geographies,
        included_geographies=country_essential_rates.keys(),
        population_by_geo=population_by_geo,
        gdp_ppp_by_geo=gdp_ppp_by_geo,
        consumption_ppp_by_geo=consumption_ppp_by_geo,
    )

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography="GLOBAL",
        period=period,
        value=consumption_weighted,
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
        metadata={},
    )
