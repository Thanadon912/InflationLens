"""Global Indicator 5 -- Global Excess Money Growth.

GLOBAL_INFLATION_METHODS.md section 9 / CALCULATION_ENGINE_GUIDELINES.md
section 9.5.

Question answered: is global broad money expanding faster than global
real output? The selected method (aggregate-first vs country-first) must
come from configuration and be returned in metadata (GLOBAL guidelines
section 9's requirement, mirroring ENGINE guidelines section 9.5).
"""

from __future__ import annotations

from collections.abc import Mapping

from app.engines.shared.aggregation import weighted_arithmetic_mean
from app.engines.shared.coverage import build_coverage_report
from app.engines.shared.errors import MissingRequiredInputError, UnsupportedMethodError
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance

INDICATOR_ID = "global_excess_money_growth"
METHODOLOGY_VERSION = "1.0.0"
SUPPORTED_METHODS = ("aggregate_first", "country_first")


def calculate(
    *,
    method: str,
    all_geographies: tuple[str, ...],
    period: str,
    calculated_at: str,
    global_money_expansion_percent: float | None = None,
    global_real_gdp_growth_percent: float | None = None,
    country_money_growth: Mapping[str, float] | None = None,
    country_real_gdp_growth: Mapping[str, float] | None = None,
    country_weights: Mapping[str, float] | None = None,
    country_velocity_adjusted_mp: Mapping[str, float] | None = None,
    money_weight_basis: str | None = None,
    gdp_weight_basis: str | None = None,
    population_by_geo: Mapping[str, float] | None = None,
    gdp_ppp_by_geo: Mapping[str, float] | None = None,
    consumption_ppp_by_geo: Mapping[str, float] | None = None,
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    if method not in SUPPORTED_METHODS:
        raise UnsupportedMethodError(method=method, context=INDICATOR_ID)

    warnings: list[str] = []
    included_geographies: set[str] = set()

    if method == "aggregate_first":
        if global_money_expansion_percent is None or global_real_gdp_growth_percent is None:
            raise MissingRequiredInputError(
                f"{INDICATOR_ID}: aggregate_first requires global_money_expansion_percent "
                "and global_real_gdp_growth_percent"
            )
        value = global_money_expansion_percent - global_real_gdp_growth_percent
        included_geographies = set(all_geographies)
    else:  # country_first
        if not (country_money_growth and country_real_gdp_growth and country_weights):
            raise MissingRequiredInputError(
                f"{INDICATOR_ID}: country_first requires country_money_growth, "
                "country_real_gdp_growth, and country_weights"
            )
        common = set(country_money_growth) & set(country_real_gdp_growth) & set(country_weights)
        country_emg = {c: country_money_growth[c] - country_real_gdp_growth[c] for c in common}
        renormalized_weights = {c: country_weights[c] for c in common}
        value = weighted_arithmetic_mean(country_emg, renormalized_weights)
        included_geographies = common

    if money_weight_basis and gdp_weight_basis and money_weight_basis != gdp_weight_basis:
        warnings.append(
            f"{INDICATOR_ID}: money weight basis ({money_weight_basis!r}) differs from "
            f"GDP weight basis ({gdp_weight_basis!r}); result mixes weighting systems "
            "(GLOBAL guidelines section 9.6)"
        )

    components = []
    if country_velocity_adjusted_mp and country_weights:
        common_mp = set(country_velocity_adjusted_mp) & set(country_weights)
        gmp_weights = {c: country_weights[c] for c in common_mp}
        gmp_values = {c: country_velocity_adjusted_mp[c] for c in common_mp}
        gmp = weighted_arithmetic_mean(gmp_values, gmp_weights)
        components.append(
            Component(
                key="global_velocity_adjusted_pressure",
                label="Global Velocity-Adjusted Monetary Pressure",
                value=gmp,
                unit=Unit.PERCENT_YOY,
            )
        )

    coverage_report = build_coverage_report(
        all_geographies=all_geographies,
        included_geographies=included_geographies,
        population_by_geo=population_by_geo,
        gdp_ppp_by_geo=gdp_ppp_by_geo,
        consumption_ppp_by_geo=consumption_ppp_by_geo,
    )

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography="GLOBAL",
        period=period,
        value=value,
        unit=Unit.PERCENT_YOY,
        method=f"excess_money_growth_{method}",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.FULL if not coverage_report.missing_geographies else Coverage.PARTIAL,
        confidence=Confidence.HIGH,
        is_estimated=False,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=tuple(components),
        coverage_report=coverage_report,
        config_version=config_version,
        metadata={"selected_method": method},
    )
