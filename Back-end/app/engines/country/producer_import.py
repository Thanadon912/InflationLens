"""Indicator 8 -- Producer and Import Inflation.

COUNTRY_INFLATION_METHODS.md section 11 / CALCULATION_ENGINE_GUIDELINES.md
section 8.8.

Question answered: what upstream cost pressures may later affect consumer
prices, company margins, or economic activity? A rise here must not be
treated as future CPI with one-to-one pass-through (COUNTRY guidelines
section 11.7).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.engines.shared.aggregation import weighted_arithmetic_mean
from app.engines.shared.errors import DataQualityError
from app.engines.shared.growth import year_over_year
from app.engines.shared.quality import derive_confidence
from app.engines.shared.standardization import historical_mean_std, z_score
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance
from app.models.observation import Observation

INDICATOR_ID = "producer_import_inflation"
METHODOLOGY_VERSION = "1.0.2"


@dataclass(frozen=True)
class ProducerImportConfig:
    """Component weights for the upstream pressure basket (COUNTRY
    guidelines section 11.6). Sourced from a country profile -- never
    hard-coded."""

    component_weights: Mapping[str, float]  # keys: ppi, import, energy, commodity


def calculate(
    *,
    ppi_current: float,
    ppi_prior_year: float,
    import_price_current: float,
    import_price_prior_year: float,
    energy_inflation_percent: float,
    commodity_inflation_percent: float,
    config: ProducerImportConfig,
    geography: str,
    period: str,
    calculated_at: str,
    foreign_price_growth_percent: float | None = None,
    exchange_rate_growth_percent: float | None = None,
    upp_standardization_window: Sequence[float] | None = None,
    source_observations: tuple[Observation, ...] = (),
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    ppi_inflation = year_over_year(ppi_current, ppi_prior_year)
    import_inflation = year_over_year(import_price_current, import_price_prior_year)

    warnings: list[str] = []
    components = [
        Component(key="ppi_inflation", label="Producer-Price Inflation", value=ppi_inflation, unit=Unit.PERCENT_YOY),
        Component(key="import_inflation", label="Import-Price Inflation", value=import_inflation, unit=Unit.PERCENT_YOY),
    ]

    if foreign_price_growth_percent is not None and exchange_rate_growth_percent is not None:
        g_star = foreign_price_growth_percent / 100
        g_e = exchange_rate_growth_percent / 100
        exact = ((1 + g_star) * (1 + g_e) - 1) * 100
        approx = foreign_price_growth_percent + exchange_rate_growth_percent
        components.append(
            Component(
                key="exchange_rate_pass_through_exact",
                label="Local-Currency Import-Cost Growth (exact)",
                value=exact,
                unit=Unit.PERCENT_YOY,
            )
        )
        components.append(
            Component(
                key="exchange_rate_pass_through_approx",
                label="Local-Currency Import-Cost Growth (approximation)",
                value=approx,
                unit=Unit.PERCENT_YOY,
            )
        )
    else:
        warnings.append(f"{INDICATOR_ID}: exchange_rate_pass_through unavailable (missing foreign price/FX growth)")

    rates = {
        "ppi": ppi_inflation,
        "import": import_inflation,
        "energy": energy_inflation_percent,
        "commodity": commodity_inflation_percent,
    }
    upp = weighted_arithmetic_mean(rates, config.component_weights)
    components.append(
        Component(key="upstream_pressure_basket", label="Upstream Pressure Basket (UPP)", value=upp, unit=Unit.PERCENT_YOY)
    )

    if upp_standardization_window is not None:
        try:
            if len(upp_standardization_window) < 2:
                raise DataQualityError("standardization window requires at least 2 values")
            mu, sigma = historical_mean_std(upp_standardization_window)
            score = z_score(upp, mu, sigma)
            components.append(
                Component(
                    key="upstream_pressure_score",
                    label="Upstream Pressure Score",
                    value=score,
                    unit=Unit.STANDARD_DEVIATION_SCORE,
                    is_score=True,
                )
            )
        except DataQualityError as exc:
            warnings.append(f"upstream_pressure_score unavailable: {exc.message}")

    confidence = derive_confidence(*source_observations) if source_observations else Confidence.HIGH
    is_estimated = any(o.is_estimated for o in source_observations)

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography=geography,
        period=period,
        value=upp,
        unit=Unit.PERCENT_YOY,
        method="upstream_pressure_weighted_basket",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.FULL if not warnings else Coverage.PARTIAL,
        confidence=confidence,
        is_estimated=is_estimated,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=tuple(components),
        config_version=config_version,
        metadata={
            "interpretation": "leading/margin-pressure indicator; pass-through to consumers is not one-to-one",
            "component_weights": dict(config.component_weights),
        },
    )
