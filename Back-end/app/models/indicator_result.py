"""The result contract every calculation returns.

Mirrors CALCULATION_ENGINE_GUIDELINES.md section 12: every indicator result
must expose both a value and its context (method, methodology version,
provenance, coverage, confidence, estimate flag, warnings, timestamp).

Several indicators are explicitly multi-valued and must **not** be
collapsed into one number:

- Underlying Inflation (COUNTRY_INFLATION_METHODS.md section 5) reports a
  ``selected_value`` plus every computed method's value.
- Housing Inflation (section 8) forbids averaging rent, house-price,
  mortgage-payment inflation, and housing burden into one rate.
- Economy-Wide Inflation (section 12) must return the GDP deflator and
  domestic-demand deflator separately, never averaged.

``IndicatorResult.value``/``unit`` hold the single headline number when an
indicator has one (e.g. Headline Consumer Inflation's YoY rate).
``components`` holds every named sub-result — including the headline one,
for uniform access — so nothing the methodology requires is ever dropped.
When an indicator has no defensible single headline number, ``value`` is
``None`` and callers must read ``components``.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.engines.shared.errors import DataQualityError
from app.models.coverage import CoverageReport
from app.models.enums import Confidence, Coverage, Unit
from app.models.methodology import InputProvenance


@dataclass(frozen=True)
class Component:
    """One named sub-value inside an :class:`IndicatorResult`.

    ``is_score`` marks values that are standardized pressure/composite
    scores rather than inflation rates (ENGINE guidelines section 19,
    COUNTRY section 8.7, GLOBAL section 10.6) — such components must use
    ``Unit.STANDARD_DEVIATION_SCORE`` and must never be presented as a
    rate.
    """

    key: str
    label: str
    value: float | None
    unit: Unit
    is_estimated: bool = False
    is_score: bool = False
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.value is not None and not math.isfinite(self.value):
            raise DataQualityError(
                f"Component {self.key!r} value must be finite, got {self.value!r}",
                key=self.key,
            )
        if self.is_score and self.unit != Unit.STANDARD_DEVIATION_SCORE:
            raise ValueError(
                f"Component {self.key!r} is marked is_score=True but unit is "
                f"{self.unit.value!r}, not {Unit.STANDARD_DEVIATION_SCORE.value!r}"
            )

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "unit": self.unit.value,
            "is_estimated": self.is_estimated,
            "is_score": self.is_score,
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class IndicatorResult:
    """A complete, self-describing calculation result."""

    indicator_id: str
    geography: str
    period: str
    value: float | None
    unit: Unit | None
    method: str
    methodology_version: str
    input_series: tuple[InputProvenance, ...]
    coverage: Coverage
    confidence: Confidence
    is_estimated: bool
    warnings: tuple[str, ...]
    calculated_at: str
    components: tuple[Component, ...] = ()
    coverage_report: CoverageReport | None = None
    config_version: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.value is not None and not math.isfinite(self.value):
            raise DataQualityError(
                f"IndicatorResult {self.indicator_id!r} value must be finite, got {self.value!r}",
                indicator=self.indicator_id,
                geography=self.geography,
                period=self.period,
            )
        if self.value is not None and self.unit is None:
            raise ValueError("IndicatorResult.unit is required whenever value is not None")
        if self.coverage == Coverage.UNAVAILABLE and self.value is not None:
            raise ValueError(
                "IndicatorResult.value must be None when coverage is 'unavailable' "
                "(ENGINE guidelines section 13: do not return a value when calculation fails)"
            )

    @classmethod
    def unavailable(
        cls,
        *,
        indicator_id: str,
        geography: str,
        period: str,
        method: str,
        methodology_version: str,
        calculated_at: str,
        reason: str,
        config_version: str | None = None,
        input_series: tuple[InputProvenance, ...] = (),
    ) -> "IndicatorResult":
        """Build a result representing "could not be calculated".

        Used by dashboard-style endpoints that must keep serving the
        indicators that *can* be computed even when one indicator's inputs
        are missing (ENGINE guidelines section 10.1-10.2: missing data
        stays missing, it is never invented or defaulted to zero).
        """

        return cls(
            indicator_id=indicator_id,
            geography=geography,
            period=period,
            value=None,
            unit=None,
            method=method,
            methodology_version=methodology_version,
            input_series=input_series,
            coverage=Coverage.UNAVAILABLE,
            confidence=Confidence.LOW,
            is_estimated=False,
            warnings=(reason,),
            calculated_at=calculated_at,
            config_version=config_version,
        )

    def to_dict(self) -> dict:
        return {
            "indicator_id": self.indicator_id,
            "geography": self.geography,
            "period": self.period,
            "value": self.value,
            "unit": self.unit.value if self.unit is not None else None,
            "method": self.method,
            "methodology_version": self.methodology_version,
            "input_series": [p.to_dict() for p in self.input_series],
            "coverage": self.coverage.value,
            "confidence": self.confidence.value,
            "is_estimated": self.is_estimated,
            "warnings": list(self.warnings),
            "calculated_at": self.calculated_at,
            "components": [c.to_dict() for c in self.components],
            "coverage_report": self.coverage_report.to_dict() if self.coverage_report else None,
            "config_version": self.config_version,
            "metadata": dict(self.metadata),
        }
