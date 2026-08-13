"""Weight renormalization and coverage-threshold gating.

CALCULATION_ENGINE_GUIDELINES.md section 10.3 permits renormalizing
weights over the available (non-missing) components only when coverage
exceeds a configured threshold, the missing components are not
structurally dominant, the result is labeled partial, and both the
original and adjusted weights are stored. This module implements the
mechanical parts of that rule; callers (engine modules) are responsible
for actually labeling results ``partial`` and storing both weight sets on
the returned ``IndicatorResult``/``CoverageReport``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal

from app.engines.shared.errors import CoverageThresholdError, InvalidWeightError
from app.models.coverage import CoverageReport


def renormalize_weights(
    weights: Mapping[str, float], available_keys: Iterable[str]
) -> dict[str, float]:
    """w*_i = w_i / sum_{j in A} w_j for i in A, where A is the available set.

    ENGINE guidelines section 10.3 / COUNTRY guidelines section 3.8 /
    GLOBAL guidelines section 3.5.
    """

    available = set(available_keys)
    unknown = available - set(weights)
    if unknown:
        raise InvalidWeightError(
            "renormalize_weights: available_keys contains keys not present in weights",
            unknown_keys=sorted(unknown),
        )
    subset = {k: v for k, v in weights.items() if k in available}
    total = sum((Decimal(str(value)) for value in subset.values()), Decimal("0"))
    if total <= 0:
        raise InvalidWeightError(
            "renormalize_weights: available components have zero total weight",
            available_keys=sorted(available),
        )
    return {k: float(Decimal(str(v)) / total) for k, v in subset.items()}


def coverage_percent(available_measure: float, total_measure: float) -> float:
    """Generic coverage percentage: available / total * 100.

    Used for population, GDP-PPP, and consumption-PPP coverage (GLOBAL
    guidelines section 14.1).
    """

    if total_measure <= 0:
        raise InvalidWeightError(
            f"coverage_percent: total_measure must be positive, got {total_measure}"
        )
    return (available_measure / total_measure) * 100


def check_coverage_threshold(
    coverage_pct: float, threshold_pct: float, *, context: str
) -> None:
    """Raise ``CoverageThresholdError`` if coverage falls below the
    configured minimum.

    ENGINE guidelines section 10.4 gives suggested defaults (e.g. 85% for
    consumption/GDP PPP coverage, 80% for population coverage); the actual
    threshold values are supplied by the caller from configuration, never
    hard-coded here (ENGINE guidelines section 11: "coverage thresholds"
    must remain outside calculation code).
    """

    if coverage_pct < threshold_pct:
        raise CoverageThresholdError(
            f"{context}: coverage {coverage_pct:.2f}% is below the required "
            f"threshold {threshold_pct:.2f}%",
            context=context,
            coverage_pct=coverage_pct,
            threshold_pct=threshold_pct,
        )


def build_coverage_report(
    *,
    all_geographies: Iterable[str],
    included_geographies: Iterable[str],
    population_by_geo: Mapping[str, float] | None = None,
    gdp_ppp_by_geo: Mapping[str, float] | None = None,
    consumption_ppp_by_geo: Mapping[str, float] | None = None,
    original_weights: Mapping[str, float] | None = None,
    adjusted_weights: Mapping[str, float] | None = None,
) -> CoverageReport:
    """Build a :class:`CoverageReport` from raw per-geography measures.

    GLOBAL guidelines section 2.5 requires every global result to report
    included-country count, population/GDP/consumption coverage, the
    missing-country list, and whether weights were renormalized; section
    14.1 gives the coverage-percentage formulas this function applies. Any
    measure mapping that is ``None`` or sums to zero yields a ``None``
    coverage percentage rather than a fabricated number.
    """

    all_set = set(all_geographies)
    included_set = set(included_geographies) & all_set
    missing = tuple(sorted(all_set - included_set))

    def _pct(by_geo: Mapping[str, float] | None) -> float | None:
        if not by_geo:
            return None
        total = sum(by_geo.get(g, 0.0) for g in all_set)
        available = sum(by_geo.get(g, 0.0) for g in included_set)
        if total <= 0:
            return None
        return coverage_percent(available, total)

    original_weights = dict(original_weights or {})
    adjusted_weights = dict(adjusted_weights or {})
    renormalized = bool(original_weights) and original_weights != adjusted_weights

    return CoverageReport(
        included_geographies=tuple(sorted(included_set)),
        missing_geographies=missing,
        population_coverage_percent=_pct(population_by_geo),
        gdp_ppp_coverage_percent=_pct(gdp_ppp_by_geo),
        consumption_ppp_coverage_percent=_pct(consumption_ppp_by_geo),
        weights_renormalized=renormalized,
        original_weights=original_weights,
        adjusted_weights=adjusted_weights,
    )
