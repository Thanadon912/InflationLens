"""Global Indicator 4 -- Global Monetary Expansion.

GLOBAL_INFLATION_METHODS.md section 8 / CALCULATION_ENGINE_GUIDELINES.md
section 9.4.

Question answered: how quickly are broad money aggregates expanding
across the global financial system? GLOBAL guidelines section 8.5
explicitly forbids converting national money stocks to USD before
computing the default growth measure -- this module only ever aggregates
already-computed local-currency growth *rates*, never raw money-stock
levels, so that mistake is structurally impossible here.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.engines.shared.aggregation import weighted_arithmetic_mean, weighted_geometric_mean_rates
from app.engines.shared.coverage import build_coverage_report
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance

INDICATOR_ID = "global_monetary_expansion"
METHODOLOGY_VERSION = "1.0.1"


def calculate(
    *,
    country_money_growth_rates: Mapping[str, float],
    gdp_ppp_weights: Mapping[str, float],
    all_geographies: tuple[str, ...],
    period: str,
    calculated_at: str,
    consumption_ppp_weights: Mapping[str, float] | None = None,
    population_by_geo: Mapping[str, float] | None = None,
    gdp_ppp_by_geo: Mapping[str, float] | None = None,
    consumption_ppp_by_geo: Mapping[str, float] | None = None,
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """GME_t = sum_c w^GDPppp_{c,t-1} g^money_{c,t} (GLOBAL guidelines
    section 8.3), the preferred GDP-PPP-weighted form. ``country_money_growth_rates``
    must already be computed in each country's local currency (GLOBAL
    guidelines section 8.2) -- this function never sees raw money-stock
    levels or exchange rates."""

    gdp_ppp_weighted = weighted_arithmetic_mean(country_money_growth_rates, gdp_ppp_weights)

    components = []
    if consumption_ppp_weights:
        components.append(
            Component(
                key="consumption_ppp_weighted",
                label="Consumption-PPP-Weighted Global Monetary Expansion",
                value=weighted_arithmetic_mean(country_money_growth_rates, consumption_ppp_weights),
                unit=Unit.PERCENT_YOY,
            )
        )

    geometric = weighted_geometric_mean_rates(country_money_growth_rates, gdp_ppp_weights)
    components.append(
        Component(key="geometric", label="Geometric Global Monetary Expansion", value=geometric, unit=Unit.PERCENT_YOY)
    )

    coverage_report = build_coverage_report(
        all_geographies=all_geographies,
        included_geographies=country_money_growth_rates.keys(),
        population_by_geo=population_by_geo,
        gdp_ppp_by_geo=gdp_ppp_by_geo,
        consumption_ppp_by_geo=consumption_ppp_by_geo,
    )

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography="GLOBAL",
        period=period,
        value=gdp_ppp_weighted,
        unit=Unit.PERCENT_YOY,
        method="gdp_ppp_weighted_arithmetic_mean",
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
        metadata={"label": "Global Monetary Expansion", "currency_conversion_applied": False},
    )
