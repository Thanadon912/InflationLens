"""Coverage reporting for global (cross-country) indicators.

GLOBAL_INFLATION_METHODS.md section 2.5 requires every global result to
report the number of included countries, population/GDP/consumption
coverage, the missing-country list, and whether weights were renormalized.
Section 14.1 gives the exact coverage-percentage formulas this model's
fields are meant to hold the *result* of (the formulas themselves live in
``app.engines.shared.coverage``).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CoverageReport:
    """Disclosure of how much of the world a global aggregate covers."""

    included_geographies: tuple[str, ...]
    missing_geographies: tuple[str, ...]
    population_coverage_percent: float | None = None
    gdp_ppp_coverage_percent: float | None = None
    consumption_ppp_coverage_percent: float | None = None
    weights_renormalized: bool = False
    original_weights: dict[str, float] = field(default_factory=dict)
    adjusted_weights: dict[str, float] = field(default_factory=dict)

    @property
    def included_count(self) -> int:
        return len(self.included_geographies)

    def to_dict(self) -> dict:
        return {
            "included_countries": self.included_count,
            "included_geographies": list(self.included_geographies),
            "missing_geographies": list(self.missing_geographies),
            "population_coverage_percent": self.population_coverage_percent,
            "gdp_ppp_coverage_percent": self.gdp_ppp_coverage_percent,
            "consumption_ppp_coverage_percent": self.consumption_ppp_coverage_percent,
            "weights_renormalized": self.weights_renormalized,
            "original_weights": dict(self.original_weights),
            "adjusted_weights": dict(self.adjusted_weights),
        }
