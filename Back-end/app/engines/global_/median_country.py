"""Global Indicator 2 -- Median Country Inflation.

GLOBAL_INFLATION_METHODS.md section 6 / CALCULATION_ENGINE_GUIDELINES.md
section 9.2.

Question answered: what inflation rate is experienced by the country in
the middle of the global distribution? GLOBAL guidelines section 6.4/14.3
forbid removing hyperinflation observations: they must remain visible in
this indicator (median/percentiles are the documented robustness view,
not a filter).
"""

from __future__ import annotations

from collections.abc import Mapping

from app.engines.shared.aggregation import (
    interquartile_range,
    percentile,
    unweighted_median,
    weighted_median,
)
from app.engines.shared.coverage import build_coverage_report
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance

INDICATOR_ID = "median_country_inflation"
METHODOLOGY_VERSION = "1.0.1"


def calculate(
    *,
    country_rates: Mapping[str, float],
    all_geographies: tuple[str, ...],
    period: str,
    calculated_at: str,
    country_weights: Mapping[str, float] | None = None,
    population_by_geo: Mapping[str, float] | None = None,
    gdp_ppp_by_geo: Mapping[str, float] | None = None,
    consumption_ppp_by_geo: Mapping[str, float] | None = None,
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    values = list(country_rates.values())
    median_value = unweighted_median(values)

    components = [
        Component(key="p25", label="25th Percentile", value=percentile(values, 25), unit=Unit.PERCENT_YOY),
        Component(key="p75", label="75th Percentile", value=percentile(values, 75), unit=Unit.PERCENT_YOY),
        Component(key="iqr", label="Interquartile Range", value=interquartile_range(values), unit=Unit.PERCENT_YOY),
        Component(key="min", label="Minimum", value=min(values), unit=Unit.PERCENT_YOY),
        Component(key="max", label="Maximum", value=max(values), unit=Unit.PERCENT_YOY),
        Component(key="count", label="Country Count", value=float(len(values)), unit=Unit.RATIO),
    ]

    if country_weights:
        components.append(
            Component(
                key="weighted_median",
                label="Weighted Median",
                value=weighted_median(country_rates, country_weights),
                unit=Unit.PERCENT_YOY,
            )
        )

    coverage_report = build_coverage_report(
        all_geographies=all_geographies,
        included_geographies=country_rates.keys(),
        population_by_geo=population_by_geo,
        gdp_ppp_by_geo=gdp_ppp_by_geo,
        consumption_ppp_by_geo=consumption_ppp_by_geo,
    )

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography="GLOBAL",
        period=period,
        value=median_value,
        unit=Unit.PERCENT_YOY,
        method="unweighted_median",
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
        metadata={"hyperinflation_observations_retained": True},
    )
