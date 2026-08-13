"""Indicator 9 -- Economy-Wide Inflation.

COUNTRY_INFLATION_METHODS.md section 12 / CALCULATION_ENGINE_GUIDELINES.md
section 8.9.

Question answered: how much are prices changing across the country's
total domestic production or domestic demand? The GDP deflator and
domestic-demand deflator answer different economic questions, so COUNTRY
guidelines section 12.5 forbids averaging them: "Do not average them
automatically." ``value``/``unit`` are therefore always ``None``; both
deflators live in ``components``.
"""

from __future__ import annotations

from app.engines.shared.growth import year_over_year
from app.engines.shared.quality import derive_confidence
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance
from app.models.observation import Observation

INDICATOR_ID = "economy_wide_inflation"
METHODOLOGY_VERSION = "1.0.0"


def gdp_deflator(nominal_gdp: float, real_gdp: float) -> float:
    """GDPDeflator_t = NominalGDP_t / RealGDP_t x 100 (COUNTRY guidelines
    section 12.2)."""

    if real_gdp <= 0:
        from app.engines.shared.errors import DataQualityError

        raise DataQualityError(f"real_gdp must be positive, got {real_gdp}")
    return (nominal_gdp / real_gdp) * 100


def calculate(
    *,
    nominal_gdp_current: float,
    real_gdp_current: float,
    nominal_gdp_prior_year: float,
    real_gdp_prior_year: float,
    geography: str,
    period: str,
    calculated_at: str,
    nominal_domestic_demand_current: float | None = None,
    real_domestic_demand_current: float | None = None,
    nominal_domestic_demand_prior_year: float | None = None,
    real_domestic_demand_prior_year: float | None = None,
    source_observations: tuple[Observation, ...] = (),
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    deflator_current = gdp_deflator(nominal_gdp_current, real_gdp_current)
    deflator_prior = gdp_deflator(nominal_gdp_prior_year, real_gdp_prior_year)
    gdp_deflator_inflation = year_over_year(deflator_current, deflator_prior)

    components = [
        Component(
            key="gdp_deflator_inflation",
            label="GDP Deflator Inflation",
            value=gdp_deflator_inflation,
            unit=Unit.PERCENT_YOY,
        ),
    ]

    warnings: list[str] = []
    domestic_demand_deflator_inflation = None
    if all(
        v is not None
        for v in (
            nominal_domestic_demand_current,
            real_domestic_demand_current,
            nominal_domestic_demand_prior_year,
            real_domestic_demand_prior_year,
        )
    ):
        dd_deflator_current = gdp_deflator(nominal_domestic_demand_current, real_domestic_demand_current)
        dd_deflator_prior = gdp_deflator(nominal_domestic_demand_prior_year, real_domestic_demand_prior_year)
        domestic_demand_deflator_inflation = year_over_year(dd_deflator_current, dd_deflator_prior)
        components.append(
            Component(
                key="domestic_demand_deflator_inflation",
                label="Domestic Demand Deflator Inflation",
                value=domestic_demand_deflator_inflation,
                unit=Unit.PERCENT_YOY,
            )
        )
    else:
        warnings.append(
            f"{INDICATOR_ID}: domestic_demand_deflator_inflation unavailable (missing C+I+G nominal/real data)"
        )

    confidence = derive_confidence(*source_observations) if source_observations else Confidence.HIGH
    is_estimated = any(o.is_estimated for o in source_observations)

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography=geography,
        period=period,
        value=None,
        unit=None,
        method="deflator_year_over_year",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.FULL if domestic_demand_deflator_inflation is not None else Coverage.PARTIAL,
        confidence=confidence,
        is_estimated=is_estimated,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=tuple(components),
        config_version=config_version,
        metadata={"note": "GDP deflator and domestic-demand deflator are never averaged; they answer different questions"},
    )
