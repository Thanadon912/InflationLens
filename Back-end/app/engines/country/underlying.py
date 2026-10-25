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
from typing import Protocol
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
METHODOLOGY_VERSION = "1.0.1"

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

class UnderlyingMethod(Protocol):
    component_rates: Mapping[str, float]
    component_weights: Mapping[str, float]

    def compute(x: UnderlyingInputs) -> float: ...

@dataclass(frozen=True)
class UnderlyingInputs:
    component_rates: Mapping[str, float]
    component_weights: Mapping[str, float]

@dataclass(frozen=True)
class WeightedMedian:
    name: str = "weighted_median"
    component_key: str = "weighted_median_value"

    def compute(self, x: UnderlyingInputs) -> float:
        return weighted_median(x.component_rates, x.component_weights,)

@dataclass(frozen=True)
class TrimmedMean:
    alpha: float = 0.1
    beta: float = 0.1
    name: str = "trimmed_mean"
    component_key: str = "trimmed_mean_value"
    boundary_handling: str = "exclude_whole"

    def compute(self, x: UnderlyingInputs) -> float:
        return trimmed_mean(
            x.component_rates, x.component_weights,
            alpha=self.alpha, beta=self.beta,
            boundary_handling=self.boundary_handling,
        )[0]
        

@dataclass(frozen=True)
class OfficialCore:
    excluded_categories: tuple[str, ...]
    official_value: float | None
    name: str = "official_core"
    component_key: str = "core_value"

    def compute(self, x: UnderlyingInputs) -> float:
        if self.official_value:
            return self.official_value
        return _core_exclusion(x.component_rates, x.component_weights, self.excluded_categories,)

@dataclass(frozen=True)
class ModelBased:
    name: str = "model_based"
    component_key: str = "model_based_value"

    def compute(self, x: UnderlyingInputs) -> float:
        raise UnsupportedMethodError(method="model_based", context="factor model not implemented in v1")

def build_methods(
        config: UnderlyingConfig,
        official_core_value: float | None = None
) -> dict[str, UnderlyingMethod]:
    return {
        "weighted_median":  WeightedMedian(),
        "trimmed_mean": TrimmedMean(
            alpha=config.trim_alpha,
            beta=config.trim_beta,
            boundary_handling=config.trim_boundary_handling,
        ),
        "official_core": OfficialCore(
            config.excluded_categories,
            official_value=official_core_value
        ),
        "model_based": ModelBased(),
    }

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

    inputs = UnderlyingInputs(component_rates, component_weights)

    methods = build_methods(config, official_core_value)
    for name, method in methods.items():
        values[name] = _safe(lambda m=method: m.compute(inputs), name, warnings)

    selected_method, selected_value = _select(config, values)

    components = tuple(
        Component(
            key=method.component_key,
            label=method.name.replace("_", " ").title(),
            value=values.get(method.name),
            unit=Unit.PERCENT_YOY,
        )
        for method in methods.values()
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

def _select(config: UnderlyingConfig, values: Mapping[str, float | None]) -> tuple[str | None, float | None]:
    candidates = [config.preferred_method, *config.fallback_methods]
    for method in candidates:
        if method in values and values[method] is not None:
            return method, values[method]
    return None, None
