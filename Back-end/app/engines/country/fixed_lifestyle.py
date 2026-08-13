"""Indicator 4 -- Fixed-Lifestyle Inflation.

COUNTRY_INFLATION_METHODS.md section 7 / CALCULATION_ENGINE_GUIDELINES.md
section 8.4.

Question answered: how much more would it cost to preserve the same
consumption pattern or lifestyle as in the reference period? This
indicator prices the *original* reference-period basket even when a
household is later forced to substitute toward cheaper goods, so forced
substitution is never mistaken for a cost improvement.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.engines.shared.aggregation import laspeyres_price_index
from app.engines.shared.errors import DataQualityError
from app.engines.shared.growth import year_over_year
from app.engines.shared.quality import derive_confidence
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance
from app.models.observation import Observation

INDICATOR_ID = "fixed_lifestyle_inflation"
METHODOLOGY_VERSION = "1.0.0"

# COUNTRY guidelines section 7.5 product-replacement hierarchy, most to
# least confident.
REPLACEMENT_HIERARCHY: tuple[str, ...] = (
    "identical_product",
    "same_brand_size",
    "same_spec_quality",
    "closest_equivalent",
    "category_proxy",
)

_REPLACEMENT_CONFIDENCE: dict[str, Confidence] = {
    "identical_product": Confidence.HIGH,
    "same_brand_size": Confidence.HIGH,
    "same_spec_quality": Confidence.MEDIUM,
    "closest_equivalent": Confidence.MEDIUM,
    "category_proxy": Confidence.LOW,
}

_CONFIDENCE_RANK = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}


@dataclass(frozen=True)
class ItemReplacement:
    """Records that ``item_id`` was priced via a substitute rather than
    the original reference-period product (COUNTRY guidelines section
    7.5)."""

    item_id: str
    replacement_level: str
    note: str = ""

    def __post_init__(self) -> None:
        if self.replacement_level not in REPLACEMENT_HIERARCHY:
            raise DataQualityError(
                f"Unknown replacement_level {self.replacement_level!r}; must be one of "
                f"{REPLACEMENT_HIERARCHY}"
            )


@dataclass(frozen=True)
class FixedLifestyleConfig:
    basket_version: str
    replacement_hierarchy: tuple[str, ...] = REPLACEMENT_HIERARCHY


def calculate(
    *,
    prices_current: Mapping[str, float],
    prices_prior_year: Mapping[str, float],
    prices_base: Mapping[str, float],
    quantities_base: Mapping[str, float],
    config: FixedLifestyleConfig,
    geography: str,
    period: str,
    calculated_at: str,
    package_sizes_current: Mapping[str, float] | None = None,
    package_sizes_base: Mapping[str, float] | None = None,
    replacements: Mapping[str, ItemReplacement] | None = None,
    quality_adjustment_factors: Mapping[str, float] | None = None,
    source_observations: tuple[Observation, ...] = (),
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """Compute Fixed-Lifestyle Inflation for one country-period.

    ``prices_base``/``quantities_base`` define the fixed reference basket.
    ``prices_current`` and ``prices_prior_year`` are two price snapshots
    (this period and twelve months earlier) of that same basket, priced at
    the substitute item where the original was discontinued (record such
    substitutions in ``replacements``).
    """

    replacements = replacements or {}

    fli_current = laspeyres_price_index(prices_current, prices_base, quantities_base)
    fli_prior_year = laspeyres_price_index(prices_prior_year, prices_base, quantities_base)
    headline_value = year_over_year(fli_current, fli_prior_year)

    total_base_value = sum(prices_base[k] * quantities_base[k] for k in quantities_base)
    item_weights = {
        k: (prices_base[k] * quantities_base[k]) / total_base_value for k in quantities_base
    }

    # Item-level contribution to the base-to-current change (COUNTRY
    # guidelines section 7 "item-level contribution"): contribution_i =
    # w_i,0 * (p_i,t / p_i,0 - 1) * 100. These sum exactly to
    # fli_current - 100 because the Laspeyres index is linear in prices.
    contribution_components = tuple(
        Component(
            key=f"contribution_{item}",
            label=f"{item} contribution to basket cost change",
            value=item_weights[item] * (prices_current[item] / prices_base[item] - 1) * 100,
            unit=Unit.PERCENT_YOY,
        )
        for item in sorted(quantities_base)
    )

    # Shrinkflation-adjusted unit price (COUNTRY guidelines section 7.6).
    unit_price_components: list[Component] = []
    if package_sizes_current and package_sizes_base:
        for item in sorted(set(package_sizes_current) & set(package_sizes_base) & set(prices_current) & set(prices_base)):
            u_t = prices_current[item] / package_sizes_current[item]
            u_0 = prices_base[item] / package_sizes_base[item]
            unit_price_components.append(
                Component(
                    key=f"unit_price_{item}",
                    label=f"{item} shrinkflation-adjusted unit price inflation",
                    value=year_over_year(u_t, u_0),
                    unit=Unit.PERCENT_YOY,
                )
            )

    # Replacement coverage and quality confidence (COUNTRY guidelines
    # section 7.5/7.7).
    replaced_weight = sum(item_weights.get(item_id, 0.0) for item_id in replacements)
    replacement_coverage_percent = (1 - replaced_weight) * 100
    item_confidences = [
        _REPLACEMENT_CONFIDENCE[r.replacement_level] for r in replacements.values()
    ] or [Confidence.HIGH]
    quality_confidence = min(item_confidences, key=lambda c: _CONFIDENCE_RANK[c])

    # Two views: raw consumer-payment comparison (as-priced) vs
    # quality-adjusted (COUNTRY guidelines section 7.7). "Do not hide the
    # difference": both are always reported, even when no adjustment
    # factors were supplied (in which case they are equal, and that
    # equality is itself the disclosure).
    if quality_adjustment_factors:
        adjusted_current = {
            k: v * quality_adjustment_factors.get(k, 1.0) for k, v in prices_current.items()
        }
        fli_quality_adjusted = laspeyres_price_index(adjusted_current, prices_base, quantities_base)
    else:
        fli_quality_adjusted = fli_current

    warnings: list[str] = []
    if replacements:
        warnings.append(
            f"{INDICATOR_ID}: {len(replacements)} item(s) priced via substitution: "
            f"{sorted(replacements)}"
        )

    confidence = derive_confidence(*source_observations) if source_observations else Confidence.HIGH
    confidence = min([confidence, quality_confidence], key=lambda c: _CONFIDENCE_RANK[c])
    is_estimated = any(o.is_estimated for o in source_observations)

    components = (
        Component(key="fixed_basket_index", label="Fixed-basket price index (FLI)", value=fli_current, unit=Unit.INDEX),
        Component(
            key="fli_quality_adjusted",
            label="Quality-adjusted fixed-basket price index",
            value=fli_quality_adjusted,
            unit=Unit.INDEX,
        ),
        Component(
            key="replacement_coverage_percent",
            label="Replacement coverage",
            value=replacement_coverage_percent,
            unit=Unit.SHARE_PERCENT,
        ),
        *contribution_components,
        *unit_price_components,
    )

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography=geography,
        period=period,
        value=headline_value,
        unit=Unit.PERCENT_YOY,
        method="laspeyres_fixed_basket_year_over_year",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.PARTIAL if replacements else Coverage.FULL,
        confidence=confidence,
        is_estimated=is_estimated,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=components,
        config_version=config_version,
        metadata={
            "basket_version": config.basket_version,
            "replacements": {k: v.replacement_level for k, v in replacements.items()},
            "quality_confidence": quality_confidence.value,
        },
    )
