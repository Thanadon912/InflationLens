"""Indicator 6 -- Broad Money Expansion.

COUNTRY_INFLATION_METHODS.md section 9 / CALCULATION_ENGINE_GUIDELINES.md
section 8.6.

Question answered: how quickly is liquid money and near-money expanding
within the financial system? This is a monetary-quantity indicator, not a
consumer-price inflation rate -- COUNTRY guidelines section 9.8: "Use
'Broad Money Expansion' or 'Monetary Expansion.' Do not label the value as
'inflation' without a qualifier."
"""

from __future__ import annotations

from app.engines.shared.growth import year_over_year
from app.engines.shared.errors import DataQualityError
from app.engines.shared.quality import derive_confidence
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance
from app.models.observation import Observation

INDICATOR_ID = "broad_money_expansion"
METHODOLOGY_VERSION = "1.0.2"
LABEL = "Broad Money Expansion"

def _compute_real_gdp_growth_n_rdio_current(
        real_gdp_current: float | None,
        real_gdp_prior_year: float | None,
        money_current: float,
        money_growth: float
) -> tuple[list[Component] | None, str | None]:
    components: list[Component] = []
    if real_gdp_current is None or real_gdp_prior_year is None:
        return None, f"{INDICATOR_ID}: money_to_real_output_ratio unavailable (missing real GDP data)"
    if real_gdp_current <= 0 or real_gdp_prior_year <= 0:
        raise DataQualityError("Real GDP levels must be positive for money/output calculations")
    
    ratio_current = money_current / real_gdp_current
    components.append(
        Component(
            key="money_to_real_output_ratio",
            label="Money-to-Real-Output Ratio",
            value=ratio_current,
            unit=Unit.RATIO,
        )
    )
    real_gdp_growth = year_over_year(real_gdp_current, real_gdp_prior_year)
    components.append(
        Component(
            key="money_to_real_output_growth_approx",
            label="Money-to-Real-Output Ratio Growth (approx: g(M) - g(RealGDP))",
            value=money_growth - real_gdp_growth,
            unit=Unit.PERCENT_YOY,
        )
    )
    return components, None

def _compute_per_capita_growth(
        population_current: float | None,
        population_prior_year: float | None,
        money_current: float,
        money_prior_year: float
) -> tuple[Component | None, str | None]:
    if population_current is None or population_prior_year is None:
        return None, f"{INDICATOR_ID}: per_capita_growth unavailable (missing population data)"
    if population_current <= 0 or population_prior_year <= 0:
        raise DataQualityError("Population levels must be positive for per-capita money growth")
    
    per_capita_current = money_current / population_current
    per_capita_prior = money_prior_year / population_prior_year
    per_capita_growth = year_over_year(per_capita_current, per_capita_prior)
    components = Component(
        key="per_capita_growth",
        label="Per-Capita Money Growth",
        value=per_capita_growth,
        unit=Unit.PERCENT_YOY,
    )
    return components, None

def calculate(
    *,
    money_current: float,
    money_prior_year: float,
    aggregate_name: str,
    geography: str,
    period: str,
    calculated_at: str,
    population_current: float | None = None,
    population_prior_year: float | None = None,
    real_gdp_current: float | None = None,
    real_gdp_prior_year: float | None = None,
    source_observations: tuple[Observation, ...] = (),
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """g^money_t = (M_t / M_{t-12} - 1) x 100 (COUNTRY guidelines section
    9.3). ``aggregate_name`` (e.g. "M2", "M3") must come from
    configuration (COUNTRY guidelines section 9.2: "Store the local
    definition.")."""

    money_growth = year_over_year(money_current, money_prior_year)

    components: list[Component] = []
    warnings: list[str] = []
    comp, warn = _compute_per_capita_growth(
        population_current,
        population_prior_year,
        money_current,
        money_prior_year
    )
    if comp:
        components.append(comp)
    if warn:
        warnings.append(warn)

    comps, warn = _compute_real_gdp_growth_n_rdio_current(
        real_gdp_current,
        real_gdp_prior_year,
        money_current,
        money_growth
    )
    if comps:
        components.extend(comps)
    if warn:
        warnings.append(warn)

    confidence = derive_confidence(*source_observations) if source_observations else Confidence.HIGH
    is_estimated = any(o.is_estimated for o in source_observations)

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography=geography,
        period=period,
        value=money_growth,
        unit=Unit.PERCENT_YOY,
        method="broad_money_year_over_year",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.FULL if not warnings else Coverage.PARTIAL,
        confidence=confidence,
        is_estimated=is_estimated,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=tuple(components),
        config_version=config_version,
        metadata={"label": LABEL, "aggregate_name": aggregate_name},
    )