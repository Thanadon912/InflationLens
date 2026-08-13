"""Indicator 10 -- Purchasing-Power Squeeze.

COUNTRY_INFLATION_METHODS.md section 13 / CALCULATION_ENGINE_GUIDELINES.md
section 8.10.

Question answered: are wages or household incomes keeping up with the
prices people actually face? COUNTRY guidelines section 13.6 requires
dual reporting against both headline CPI and Essential Cost Inflation, and
section 13.7 warns that moderate headline CPI can coexist with a real
squeeze once essential-cost and housing pressures are accounted for.
"""

from __future__ import annotations

from app.engines.shared.growth import real_growth, real_growth_approx
from app.engines.shared.quality import derive_confidence
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance
from app.models.observation import Observation

INDICATOR_ID = "purchasing_power_squeeze"
METHODOLOGY_VERSION = "1.0.0"


def calculate(
    *,
    nominal_wage_growth_percent: float,
    headline_inflation_percent: float,
    essential_inflation_percent: float,
    wage_measure: str,
    income_definition: str,
    geography: str,
    period: str,
    calculated_at: str,
    disposable_income_growth_percent: float | None = None,
    source_observations: tuple[Observation, ...] = (),
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """Headline value is real wage growth deflated by headline CPI (exact
    form, COUNTRY guidelines section 13.2); every other view -- essential-
    cost-adjusted, disposable-income-adjusted, and the squeeze itself --
    is reported as a component so nothing required by section 13.6's dual
    reporting rule is ever hidden.
    """

    real_wage_headline_exact = real_growth(nominal_wage_growth_percent, headline_inflation_percent)
    real_wage_headline_approx = real_growth_approx(nominal_wage_growth_percent, headline_inflation_percent)
    real_wage_essential_exact = real_growth(nominal_wage_growth_percent, essential_inflation_percent)
    real_wage_essential_approx = real_growth_approx(nominal_wage_growth_percent, essential_inflation_percent)

    # COUNTRY guidelines section 13.5: PPS_t = pi_t - g^nominalincome_t.
    # Reported against both headline and essential inflation (mirroring
    # the dual-reporting requirement applied to real wage growth) so a
    # squeeze that is invisible under headline CPI but visible under
    # essential costs is never hidden (COUNTRY guidelines section 13.7).
    pps_headline = headline_inflation_percent - nominal_wage_growth_percent
    pps_essential = essential_inflation_percent - nominal_wage_growth_percent

    components = [
        Component(
            key="real_wage_headline_approx",
            label="Real Wage Growth vs Headline CPI (approx)",
            value=real_wage_headline_approx,
            unit=Unit.PERCENT_YOY,
        ),
        Component(
            key="real_wage_essential_exact",
            label="Real Wage Growth vs Essential Cost Inflation (exact)",
            value=real_wage_essential_exact,
            unit=Unit.PERCENT_YOY,
        ),
        Component(
            key="real_wage_essential_approx",
            label="Real Wage Growth vs Essential Cost Inflation (approx)",
            value=real_wage_essential_approx,
            unit=Unit.PERCENT_YOY,
        ),
        Component(
            key="purchasing_power_squeeze_headline",
            label="Purchasing-Power Squeeze (vs Headline CPI)",
            value=pps_headline,
            unit=Unit.PERCENT_YOY,
        ),
        Component(
            key="purchasing_power_squeeze_essential",
            label="Purchasing-Power Squeeze (vs Essential Cost Inflation)",
            value=pps_essential,
            unit=Unit.PERCENT_YOY,
        ),
    ]

    warnings: list[str] = []
    if disposable_income_growth_percent is not None:
        components.append(
            Component(
                key="real_disposable_income_growth",
                label="Real Disposable-Income Growth vs Headline CPI",
                value=real_growth(disposable_income_growth_percent, headline_inflation_percent),
                unit=Unit.PERCENT_YOY,
            )
        )
    else:
        warnings.append(f"{INDICATOR_ID}: real_disposable_income_growth unavailable (no disposable income data)")

    confidence = derive_confidence(*source_observations) if source_observations else Confidence.HIGH
    is_estimated = any(o.is_estimated for o in source_observations)

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography=geography,
        period=period,
        value=real_wage_headline_exact,
        unit=Unit.PERCENT_YOY,
        method="real_wage_growth_exact_headline",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.FULL if disposable_income_growth_percent is not None else Coverage.PARTIAL,
        confidence=confidence,
        is_estimated=is_estimated,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=tuple(components),
        config_version=config_version,
        metadata={
            "wage_measure": wage_measure,
            "income_definition": income_definition,
        },
    )
