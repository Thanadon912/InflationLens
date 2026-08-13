"""Indicator 2 -- Underlying Inflation.

COUNTRY_INFLATION_METHODS.md section 5 / CALCULATION_ENGINE_GUIDELINES.md
section 8.2.

Question answered: how broad and persistent is inflation after reducing
the influence of extreme or temporary price movements?

The engine must not choose a method based on whichever produces the
lowest or highest result (COUNTRY guidelines section 5.8); the selected
method comes entirely from ``UnderlyingConfig.preferred_method`` /
``fallback_methods``, and every computed method's value is returned
(unavailable methods are reported as unavailable, never omitted --
ENGINE guidelines section 8.2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.engines.shared.aggregation import trimmed_mean, weighted_arithmetic_mean, weighted_median
from app.engines.shared.coverage import renormalize_weights
from app.engines.shared.errors import EngineError, UnsupportedMethodError
from app.engines.shared.quality import derive_confidence
from app.models.enums import Confidence, Coverage, Unit
from app.models.indicator_result import Component, IndicatorResult
from app.models.methodology import InputProvenance
from app.models.observation import Observation

INDICATOR_ID = "underlying_inflation"
METHODOLOGY_VERSION = "1.0.0"

_METHOD_KEYS = {
    "weighted_median": "weighted_median_value",
    "trimmed_mean": "trimmed_mean_value",
    "official_core": "core_value",
    "model_based": "model_based_value",
}


@dataclass(frozen=True)
class UnderlyingConfig:
    """Externalized policy for Underlying Inflation (ENGINE guidelines
    section 8.2's YAML example; values sourced from a country profile)."""

    preferred_method: str
    fallback_methods: tuple[str, ...]
    trim_alpha: float
    trim_beta: float
    excluded_categories: tuple[str, ...]
    trim_boundary_handling: str = "exclude_whole"


def calculate(
    *,
    component_rates: Mapping[str, float],
    component_weights: Mapping[str, float],
    config: UnderlyingConfig,
    geography: str,
    period: str,
    calculated_at: str,
    official_core_value: float | None = None,
    source_observations: tuple[Observation, ...] = (),
    input_series: tuple[InputProvenance, ...] = (),
    methodology_version: str = METHODOLOGY_VERSION,
    config_version: str | None = None,
) -> IndicatorResult:
    """Compute Underlying Inflation for one country-period.

    ``component_rates``/``component_weights`` are category-level inflation
    rates (percent) and expenditure weights used for the weighted-median,
    trimmed-mean, and core-exclusion computations. ``official_core_value``
    is an optional directly-published official core rate (e.g. BLS "all
    items less food and energy"); when present it is used for the
    ``official_core`` method instead of being derived.
    """

    values: dict[str, float | None] = {}
    warnings: list[str] = []

    values["weighted_median"] = _safe(
        lambda: weighted_median(component_rates, component_weights), "weighted_median", warnings
    )
    values["trimmed_mean"] = _safe(
        lambda: trimmed_mean(
            component_rates,
            component_weights,
            alpha=config.trim_alpha,
            beta=config.trim_beta,
            boundary_handling=config.trim_boundary_handling,
        )[0],
        "trimmed_mean",
        warnings,
    )
    values["official_core"] = _safe(
        lambda: _core_exclusion(component_rates, component_weights, config.excluded_categories)
        if official_core_value is None
        else official_core_value,
        "official_core",
        warnings,
    )
    values["model_based"] = _safe(_unavailable_model_based, "model_based", warnings)

    selected_method, selected_value = _select(config, values)

    components = tuple(
        Component(
            key=_METHOD_KEYS[method],
            label=method.replace("_", " ").title(),
            value=values.get(method),
            unit=Unit.PERCENT_YOY,
        )
        for method in _METHOD_KEYS
    )

    confidence = derive_confidence(*source_observations) if source_observations else Confidence.LOW
    is_estimated = any(o.is_estimated for o in source_observations)

    return IndicatorResult(
        indicator_id=INDICATOR_ID,
        geography=geography,
        period=period,
        value=selected_value,
        unit=Unit.PERCENT_YOY if selected_value is not None else None,
        method=f"underlying_{selected_method}" if selected_method else "underlying_unavailable",
        methodology_version=methodology_version,
        input_series=input_series,
        coverage=Coverage.FULL if selected_value is not None else Coverage.UNAVAILABLE,
        confidence=confidence,
        is_estimated=is_estimated,
        warnings=tuple(warnings),
        calculated_at=calculated_at,
        components=components,
        config_version=config_version,
        metadata={"selected_method": selected_method},
    )


def _safe(fn, method_name: str, warnings: list[str]) -> float | None:
    try:
        return fn()
    except EngineError as exc:
        warnings.append(f"{method_name} unavailable: {exc.message}")
        return None


def _core_exclusion(
    component_rates: Mapping[str, float],
    component_weights: Mapping[str, float],
    excluded_categories: tuple[str, ...],
) -> float:
    """pi^core_t = sum_{i not in E} w*_i pi_{i,t} (COUNTRY guidelines
    section 5.5), with w*_i renormalized over the retained set."""

    retained_keys = [k for k in component_rates if k not in excluded_categories]
    if not retained_keys:
        raise UnsupportedMethodError(method="official_core", context="all categories excluded")
    renormalized = renormalize_weights(component_weights, retained_keys)
    retained_rates = {k: component_rates[k] for k in retained_keys}
    return weighted_arithmetic_mean(retained_rates, renormalized)


def _unavailable_model_based() -> float:
    # COUNTRY guidelines section 5.6's common-factor model requires a
    # statistical estimation procedure that is out of scope for this
    # phase; it must still be reported (as unavailable), never omitted.
    raise UnsupportedMethodError(method="model_based", context="factor model not implemented in v1")


def _select(config: UnderlyingConfig, values: Mapping[str, float | None]) -> tuple[str | None, float | None]:
    candidates = [config.preferred_method, *config.fallback_methods]
    for method in candidates:
        if method in values and values[method] is not None:
            return method, values[method]
    return None, None
