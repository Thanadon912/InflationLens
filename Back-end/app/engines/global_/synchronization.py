"""Global Indicator 8 -- Global Inflation Synchronization.

GLOBAL_INFLATION_METHODS.md section 12 / CALCULATION_ENGINE_GUIDELINES.md
section 9.8.

Question answered: how widespread and globally coordinated is inflation?
Threshold values must be configurable, and country count/coverage must
always be returned (GLOBAL guidelines section 12 rules). The common-factor
model (section 12.6) requires a statistical estimation procedure out of
scope for this phase and is always reported unavailable, versioned
separately as ENGINE guidelines section 9.8 requires.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.engines.shared.aggregation import (
    interquartile_range,
    sample_mean,
    sample_std,
    unweighted_median,
)
from app.engines.shared.coverage import build_coverage_report, renormalize_weights
from app.engines.shared.errors import DataQualityError, EngineError
from app.engines.shared.standardization import (
    composite_score,
    diffusion_z_score,
    historical_mean_std,
    z_score,
)
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance

INDICATOR_ID = "global_inflation_synchronization"
METHODOLOGY_VERSION = "1.0.2"
COMMON_FACTOR_MODEL_VERSION = "unavailable-v1"


def calculate(
    *,
    country_rates_current: Mapping[str, float],
    threshold_percent: float,
    all_geographies: tuple[str, ...],
    period: str,
    calculated_at: str,
    country_rates_prior: Mapping[str, float] | None = None,
    population_weights: Mapping[str, float] | None = None,
    composite_weights: Mapping[str, float] | None = None,
    dispersion_standardization_window: Sequence[float] | None = None,
    population_by_geo: Mapping[str, float] | None = None,
    gdp_ppp_by_geo: Mapping[str, float] | None = None,
    consumption_ppp_by_geo: Mapping[str, float] | None = None,
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    values = list(country_rates_current.values())
    count = len(values)
    if count == 0:
        raise DataQualityError("global_inflation_synchronization requires at least one country")

    share_above = (sum(1 for v in values if v > threshold_percent) / count) * 100

    components = [
        Component(key="country_count", label="Country Count", value=float(count), unit=Unit.RATIO),
        Component(key="mean", label="Cross-Country Mean", value=sample_mean(values), unit=Unit.PERCENT_YOY),
        Component(key="iqr", label="Interquartile Range", value=interquartile_range(values), unit=Unit.PERCENT_YOY),
    ]

    dispersion = None
    if count >= 2:
        dispersion = sample_std(values)
        components.append(
            Component(key="dispersion", label="Cross-Country Standard Deviation", value=dispersion, unit=Unit.PERCENT_YOY)
        )

    warnings: list[str] = []

    if population_weights:
        covered = set(country_rates_current) & set(population_weights)
        if covered:
            try:
                renormalized_pop_weights = renormalize_weights(population_weights, covered)
                share_above_pop = sum(
                    renormalized_pop_weights[c] * (1 if country_rates_current[c] > threshold_percent else 0)
                    for c in covered
                ) * 100
                components.append(
                    Component(
                        key="share_above_pop_weighted",
                        label="Population-Weighted Share Above Threshold",
                        value=share_above_pop,
                        unit=Unit.SHARE_PERCENT,
                    )
                )
                if covered != set(country_rates_current):
                    missing = sorted(set(country_rates_current) - covered)
                    warnings.append(
                        f"{INDICATOR_ID}: share_above_pop_weighted computed over {len(covered)}/{count} countries "
                        f"(no population weight for {missing})"
                    )
            except EngineError as exc:
                warnings.append(f"share_above_pop_weighted unavailable: {exc.message}")
        else:
            warnings.append(f"{INDICATOR_ID}: share_above_pop_weighted unavailable (no overlap between country_rates_current and population_weights)")

    share_accelerating = None
    if country_rates_prior:
        common = set(country_rates_current) & set(country_rates_prior)
        if common:
            accelerating = sum(1 for c in common if country_rates_current[c] > country_rates_prior[c])
            share_accelerating = (accelerating / len(common)) * 100
            components.append(
                Component(
                    key="share_accelerating",
                    label="Share of Countries with Accelerating Inflation",
                    value=share_accelerating,
                    unit=Unit.SHARE_PERCENT,
                )
            )
    else:
        warnings.append(f"{INDICATOR_ID}: share_accelerating unavailable (no prior-period rates supplied)")

    components.append(
        Component(
            key="common_factor_model",
            label="Common-Factor Synchronization Model",
            value=None,
            unit=Unit.STANDARD_DEVIATION_SCORE,
            is_score=True,
            warnings=(f"unavailable in {COMMON_FACTOR_MODEL_VERSION} (requires statistical factor estimation)",),
        )
    )

    if (
        composite_weights
        and dispersion_standardization_window
        and dispersion is not None
        and share_accelerating is not None
    ):
        try:
            if len(dispersion_standardization_window) < 2:
                raise DataQualityError("standardization window requires at least 2 historical values")
            mu, sigma = historical_mean_std(dispersion_standardization_window)
            z_dispersion = z_score(dispersion, mu, sigma)
            z_accelerating = diffusion_z_score(share_accelerating)
            z_above = diffusion_z_score(share_above)
            # GLOBAL section 12.7 standardizes diffusion shares onto the
            # standard-deviation scale ((S - 50) / 25) and subtracts
            # standardized dispersion: synchronization is weaker when
            # cross-country rates spread out.
            sync_score = composite_score(
                {
                    "share_accelerating": z_accelerating,
                    "share_above_threshold": z_above,
                    "dispersion": -z_dispersion,
                },
                composite_weights,
            )
            components.append(
                Component(
                    key="synchronization_score",
                    label="Global Inflation Synchronization Score",
                    value=sync_score,
                    unit=Unit.STANDARD_DEVIATION_SCORE,
                    is_score=True,
                )
            )
        except DataQualityError as exc:
            warnings.append(f"synchronization_score unavailable: {exc.message}")

    coverage_report = build_coverage_report(
        all_geographies=all_geographies,
        included_geographies=country_rates_current.keys(),
        population_by_geo=population_by_geo,
        gdp_ppp_by_geo=gdp_ppp_by_geo,
        consumption_ppp_by_geo=consumption_ppp_by_geo,
    )

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography="GLOBAL",
        period=period,
        value=share_above,
        unit=Unit.SHARE_PERCENT,
        method="share_above_threshold",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.FULL if not warnings else Coverage.PARTIAL,
        confidence=Confidence.HIGH,
        is_estimated=False,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=tuple(components),
        coverage_report=coverage_report,
        config_version=config_version,
        metadata={"threshold_percent": threshold_percent},
    )
