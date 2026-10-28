"""Indicator 7 -- Excess Money Growth.

COUNTRY_INFLATION_METHODS.md section 10 / CALCULATION_ENGINE_GUIDELINES.md
section 8.7.

Question answered: is broad money expanding faster than real economic
output? A positive value is a monetary-pressure signal, not a guaranteed
CPI forecast (COUNTRY guidelines section 10.6).
"""

from __future__ import annotations

from app.engines.shared.errors import EngineError
from app.engines.shared.growth import year_over_year
from app.engines.shared.periods import Period
from app.engines.shared.quality import derive_confidence
from app.engines.shared.validation import validate_period_alignment, validate_positive_index
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance
from app.models.observation import Observation

INDICATOR_ID = "excess_money_growth"
METHODOLOGY_VERSION = "1.0.1"


def calculate(
    *,
    money_growth_percent: float,
    real_output_growth_percent: float,
    money_period: Period,
    real_output_period: Period,
    geography: str,
    period: str,
    calculated_at: str,
    nominal_gdp_current: float | None = None,
    nominal_gdp_prior: float | None = None,
    money_current: float | None = None,
    money_prior: float | None = None,
    source_observations: tuple[Observation, ...] = (),
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """EMG_t = g_t(M) - g_t(Y) (COUNTRY guidelines section 10.2).
    COUNTRY guidelines section 10.7: "Do not combine monthly money growth
    with quarterly GDP growth without explicit alignment" -- enforced here
    by requiring ``money_period`` and ``real_output_period`` to refer to
    the exact same economic period (any resampling/alignment must already
    have been performed by the caller before this function is invoked, so
    it is visible in the calling code rather than hidden here).
    """

    validate_period_alignment(money_period, real_output_period, context=INDICATOR_ID)

    simple_emg = money_growth_percent - real_output_growth_percent

    components = [
        Component(
            key="broad_money_growth", label="Broad Money Growth", value=money_growth_percent, unit=Unit.PERCENT_YOY
        ),
        Component(
            key="real_output_growth", label="Real Output Growth", value=real_output_growth_percent, unit=Unit.PERCENT_YOY
        ),
    ]

    warnings: list[str] = []
    velocity_adjusted_mp = None
    if all(v is not None for v in (nominal_gdp_current, nominal_gdp_prior, money_current, money_prior)):
        try:
            validate_positive_index(money_current, context=f"{INDICATOR_ID}.money_current")
            validate_positive_index(money_prior, context=f"{INDICATOR_ID}.money_prior")
            velocity_current = nominal_gdp_current / money_current
            velocity_prior = nominal_gdp_prior / money_prior
            velocity_growth = year_over_year(velocity_current, velocity_prior)
            velocity_adjusted_mp = money_growth_percent + velocity_growth - real_output_growth_percent
            components.append(
                Component(key="velocity_growth", label="Money Velocity Growth", value=velocity_growth, unit=Unit.PERCENT_YOY)
            )
            components.append(
                Component(
                    key="velocity_adjusted_monetary_pressure",
                    label="Velocity-Adjusted Monetary Pressure",
                    value=velocity_adjusted_mp,
                    unit=Unit.PERCENT_YOY,
                )
            )
        except EngineError as exc:
            warnings.append(f"velocity_adjusted_monetary_pressure unavailable: {exc.message}")
    else:
        warnings.append(f"{INDICATOR_ID}: velocity_adjusted_monetary_pressure unavailable (missing nominal GDP/money levels)")

    confidence = derive_confidence(*source_observations) if source_observations else Confidence.HIGH
    is_estimated = any(o.is_estimated for o in source_observations)

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography=geography,
        period=period,
        value=simple_emg,
        unit=Unit.PERCENT_YOY,
        method="excess_money_growth_simple",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.FULL if velocity_adjusted_mp is not None else Coverage.PARTIAL,
        confidence=confidence,
        is_estimated=is_estimated,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=tuple(components),
        config_version=config_version,
        metadata={
            "interpretation": "monetary pressure indicator, not a guaranteed CPI forecast",
        },
    )
