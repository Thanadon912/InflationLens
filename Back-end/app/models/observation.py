"""The normalized observation contract.

Mirrors the schema in CALCULATION_ENGINE_GUIDELINES.md section 4 and
API_DATA_SOURCES_GUIDE.md section 14. This is the *only* shape of input the
calculation engine is allowed to consume — provider adapters are
responsible for producing it, but building adapters is out of scope for
this phase (see Back-end/README.md).

``Observation`` is an immutable (frozen) dataclass so that once a value
enters the engine it cannot be mutated mid-calculation; every derived value
is a new object, keeping the traceability chain in ENGINE guidelines
section 25 intact.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.engines.shared.errors import DataQualityError, SeriesDefinitionError
from app.engines.shared.periods import Period, parse_period
from app.models.enums import Confidence, Coverage, Frequency, Unit, ValidationStatus


@dataclass(frozen=True)
class Observation:
    """A single normalized data point.

    Required fields correspond to ENGINE guidelines section 4.1. Optional
    fields correspond to section 4.2 and default to ``None`` (or ``False``
    for the estimate/revision flags, since those specifically describe a
    boolean state rather than genuinely unknown metadata).
    """

    # --- Required (section 4.1) ---
    provider: str
    source_series_id: str
    indicator_id: str
    geography: str
    frequency: Frequency
    unit: Unit
    observation_period: str
    value: float
    retrieved_at: str
    validation_status: ValidationStatus

    # --- Optional but recommended (section 4.2) ---
    publication_date: str | None = None
    seasonally_adjusted: bool | None = None
    source_url: str | None = None
    is_estimated: bool = False
    is_revised: bool = False
    data_vintage: str | None = None
    methodology_version: str | None = None
    confidence: Confidence | None = None
    coverage_status: Coverage | None = None
    component_id: str | None = None
    currency: str | None = None

    _period_cache: Period = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
            raise DataQualityError(
                f"Observation value must be numeric, got {type(self.value).__name__}",
                indicator=self.indicator_id,
            )
        if not math.isfinite(self.value):
            raise DataQualityError(
                f"Observation value must be finite, got {self.value!r}",
                indicator=self.indicator_id,
                geography=self.geography,
                period=self.observation_period,
            )
        if not self.provider:
            raise SeriesDefinitionError("Observation.provider must not be empty")
        if not self.source_series_id:
            raise SeriesDefinitionError("Observation.source_series_id must not be empty")
        if not self.geography:
            raise SeriesDefinitionError("Observation.geography must not be empty")
        if self.validation_status != ValidationStatus.VALIDATED:
            raise DataQualityError(
                "Only validated observations may enter the calculation engine",
                indicator=self.indicator_id,
                geography=self.geography,
                period=self.observation_period,
                validation_status=self.validation_status.value,
            )

        period = parse_period(self.observation_period, self.frequency)
        object.__setattr__(self, "_period_cache", period)

    @property
    def period(self) -> Period:
        """The parsed, comparable :class:`Period` for this observation."""

        return self._period_cache
