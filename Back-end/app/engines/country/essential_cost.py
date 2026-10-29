"""Indicator 3 -- Essential Cost Inflation.

COUNTRY_INFLATION_METHODS.md section 6 / CALCULATION_ENGINE_GUIDELINES.md
section 8.3.

Question answered: how quickly are unavoidable or near-unavoidable
household expenses increasing?
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.engines.shared.aggregation import laspeyres_price_index, weighted_arithmetic_mean
from app.engines.shared.coverage import check_coverage_threshold, renormalize_weights
from app.engines.shared.errors import MissingRequiredInputError
from app.engines.shared.growth import year_over_year
from app.engines.shared.quality import derive_confidence
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance
from app.models.observation import Observation

INDICATOR_ID = "essential_cost_inflation"
METHODOLOGY_VERSION = "1.0.2"


@dataclass(frozen=True)
class EssentialBasketConfig:
    """The essential-category basket, sourced from a country profile
    (ENGINE guidelines section 8.3's YAML example). Weights must come
    from configuration -- never hard-coded in this module."""

    version: str
    methodology: str
    categories: Mapping[str, float]
    min_coverage_percent: float
    structurally_dominant_weight: float


def calculate_from_rates(
    category_rates: Mapping[str, float],
    config: EssentialBasketConfig,
    *,
    geography: str,
    period: str,
    calculated_at: str,
    source_observations: tuple[Observation, ...] = (),
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """pi^essential_t = sum_{i in E} w^essential_i pi_{i,t}, subject to
    sum_i w^essential_i = 1 (COUNTRY guidelines section 6.3).

    ``category_rates`` are already-computed category-level YoY inflation
    rates. If some configured categories are missing from
    ``category_rates``, weights are renormalized over the available
    categories per ENGINE guidelines section 10.3, coverage is reported as
    partial, and both original and adjusted weights are disclosed
    (COUNTRY guidelines section 6.3 validation: "missing categories
    require coverage reporting").
    """
    
    missing, provided = resolve_essential_categories(config_categories=config.categories, category_rates=category_rates)

    warnings: list[str] = []
    weights_renormalized = bool(missing)

    if missing:
        total_weight = sum(config.categories.values())
        available_weight = sum(config.categories[k] for k in provided)
        coverage_pct = (available_weight / total_weight) * 100 if total_weight > 0 else 0.0
        check_coverage_threshold(coverage_pct, config.min_coverage_percent, context=INDICATOR_ID)
        validate_no_missing_dominant_category(config=config, missing=missing)
        weights = renormalize_weights(config.categories, provided)
        warnings.append(
            f"{INDICATOR_ID}: categories missing from input, weights renormalized: "
            f"{sorted(missing)}"
        )
    else:
        weights = dict(config.categories)

    retained_rates = {k: category_rates[k] for k in provided}
    value = weighted_arithmetic_mean(retained_rates, weights)

    confidence = derive_confidence(*source_observations) if source_observations else Confidence.HIGH
    if weights_renormalized and confidence == Confidence.HIGH:
        confidence = Confidence.MEDIUM
    is_estimated = any(o.is_estimated for o in source_observations)

    components = tuple(
        Component(key=f"category_{k}", label=k.replace("_", " ").title(), value=v, unit=Unit.PERCENT_YOY)
        for k, v in sorted(retained_rates.items())
    )

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography=geography,
        period=period,
        value=value,
        unit=Unit.PERCENT_YOY,
        method="essential_basket_weighted_mean",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.PARTIAL if weights_renormalized else Coverage.FULL,
        confidence=confidence,
        is_estimated=is_estimated,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=components,
        config_version=config_version,
        metadata={
            "basket_version": config.version,
            "basket_methodology": config.methodology,
            "original_weights": dict(config.categories),
            "adjusted_weights": dict(weights),
            "weights_renormalized": weights_renormalized,
        },
    )

def resolve_essential_categories(
        category_rates:Mapping[str, float],
        config_categories: Mapping[str, float],
        indicator_id: str = INDICATOR_ID
) -> tuple[set[str], set[str]]:

    required = set(config_categories)
    provided = set(category_rates) & required
    if not provided:
        raise MissingRequiredInputError(
            f"{indicator_id}: none of the configured essential categories are present in input",
            required_categories=sorted(required),
        )

    missing = required - provided
    return missing, provided

def validate_no_missing_dominant_category(
        config: EssentialBasketConfig,
        missing: set
) -> None:
    
    max_missing_weight = max((config.categories[k] for k in missing), default=0.0)
    if max_missing_weight >= config.structurally_dominant_weight:
        from app.engines.shared.errors import CoverageThresholdError
        raise CoverageThresholdError(
            f"{INDICATOR_ID}: a structurally dominant category is missing",
            missing_categories=sorted(missing),
        )

def essential_cost_index(
    prices_current: Mapping[str, float],
    prices_base: Mapping[str, float],
    quantities_base: Mapping[str, float],
) -> float:
    """ECI_t = sum p_it q_i0 / sum p_i0 q_i0 * 100 (COUNTRY guidelines
    section 6.5), the price-level (fixed-basket) alternative to the
    rate-weighted formula in :func:`calculate_from_rates`."""

    return laspeyres_price_index(prices_current, prices_base, quantities_base)


def calculate_from_price_level(
    eci_current: float,
    eci_prior_year: float,
    *,
    geography: str,
    period: str,
    calculated_at: str,
    source_observations: tuple[Observation, ...] = (),
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """pi^essential_t = (ECI_t / ECI_{t-12} - 1) x 100 (COUNTRY guidelines
    section 6.5), given two already-computed ECI levels (see
    :func:`essential_cost_index`)."""

    value = year_over_year(eci_current, eci_prior_year)
    confidence = derive_confidence(*source_observations) if source_observations else Confidence.HIGH
    is_estimated = any(o.is_estimated for o in source_observations)

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography=geography,
        period=period,
        value=value,
        unit=Unit.PERCENT_YOY,
        method="essential_basket_fixed_price_level",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.FULL,
        confidence=confidence,
        is_estimated=is_estimated,
        warnings=(),
        calculated_at=calculated_at,
        config_version=config_version,
        metadata={"eci_current": eci_current, "eci_prior_year": eci_prior_year},
    )
