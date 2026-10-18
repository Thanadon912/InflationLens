"""Input validation shared by every engine module.

Implements the "no silent conversions" rules from
CALCULATION_ENGINE_GUIDELINES.md sections 5 (units), 6 (frequency and
period alignment), and the weight constraints repeated throughout section 7
("subject to sum_i w_i = 1"). Every check here raises a specific domain
error from ``app.engines.shared.errors`` rather than coercing or
defaulting, so a caller can never mistake a validation failure for a real
result.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.engines.shared.errors import (
    DataQualityError,
    FrequencyMismatchError,
    InsufficientHistoryError,
    InvalidWeightError,
    MissingRequiredInputError,
    PeriodAlignmentError,
    UnitMismatchError,
)
from app.engines.shared.periods import Period
from app.models.enums import Frequency, Unit
from app.models.observation import Observation
from app.models.series import ObservationSeries

DEFAULT_WEIGHT_TOLERANCE = 1e-6


def validate_unit(unit: Unit, accepted_units: Iterable[Unit], *, indicator_id: str) -> None:
    """Reject a unit unless it is one the formula explicitly declared it
    accepts (ENGINE guidelines section 5.2)."""

    accepted = set(accepted_units)
    if unit not in accepted:
        expected = ", ".join(sorted(u.value for u in accepted))
        raise UnitMismatchError(expected=expected, received=unit.value, indicator=indicator_id)


def validate_frequency(frequency: Frequency, expected: Frequency, *, indicator_id: str) -> None:
    """Reject a frequency unless it matches what the formula requires
    (ENGINE guidelines section 6.2)."""

    if frequency != expected:
        raise FrequencyMismatchError(
            expected=expected.value, received=frequency.value, indicator=indicator_id
        )


def validate_period_alignment(period_a: Period, period_b: Period, *, context: str) -> None:
    """Reject two periods that do not refer to the same economic period.

    ENGINE guidelines section 6.4: inputs "must refer to the same economic
    period or an explicitly documented lag." Any explicit lag must be
    applied by the caller *before* calling this function (e.g. by shifting
    one of the periods); this function only ever accepts an exact match,
    so any allowed lag is visible in the calling code rather than hidden
    inside validation.
    """

    if period_a.sort_key != period_b.sort_key or period_a.frequency != period_b.frequency:
        raise PeriodAlignmentError(
            f"Periods are not aligned for {context}: {period_a.raw!r} vs {period_b.raw!r}",
            context=context,
            period_a=period_a.raw,
            period_b=period_b.raw,
        )


def validate_weights(
    weights: Mapping[str, float] | Iterable[float],
    *,
    tolerance: float = DEFAULT_WEIGHT_TOLERANCE,
    context: str = "weights",
) -> None:
    """Reject weights that are empty, negative, or do not sum to one.

    ENGINE guidelines section 7.5: "subject to sum_i w_i = 1", and section
    11.1 forbids non-negative weights implicitly by requiring a valid
    probability-like distribution. Accepts either a mapping (component ->
    weight) or a plain iterable of weights.
    """

    values = list(weights.values()) if isinstance(weights, Mapping) else list(weights)
    if not values:
        raise InvalidWeightError(f"{context}: weight set must not be empty", context=context)
    for w in values:
        if w < 0:
            raise InvalidWeightError(
                f"{context}: weights must be non-negative, got {w}", context=context, weight=w
            )
    total = sum(values)
    if abs(total - 1.0) > tolerance:
        raise InvalidWeightError(
            f"{context}: weights must sum to 1 (within tolerance {tolerance}), got {total}",
            context=context,
            total=total,
            tolerance=tolerance,
        )


def validate_positive_index(value: float, *, context: str) -> None:
    """Reject a zero or negative index value.

    ENGINE guidelines section 8.1: "no zero or negative index values."
    """

    if value <= 0:
        raise DataQualityError(
            f"{context}: index value must be positive, got {value}", context=context, value=value
        )


def require_observation_at(series: ObservationSeries, period: Period, *, context: str) -> Observation:
    """Return the observation at exactly ``period`` or raise
    ``MissingRequiredInputError``."""

    obs = series.get_at(period)
    if obs is None:
        raise MissingRequiredInputError(
            f"{context}: no observation for period {period.raw!r}", context=context, period=period.raw
        )
    
    validate_positive_index(obs.value, context=context)
    return obs


def require_lagged_observation(
    series: ObservationSeries, reference: Period, lag: int, *, context: str
) -> Observation:
    """Return the observation ``lag`` native periods before ``reference``,
    or raise ``InsufficientHistoryError`` if the series does not go back
    far enough (ENGINE guidelines section 8.1: "sufficient history must
    exist")."""

    obs = series.get_lagged(reference, lag)
    if obs is None:
        target = reference.shift(-lag)
        raise InsufficientHistoryError(
            f"{context}: no observation for required period {target.raw!r} "
            f"(reference {reference.raw!r}, lag {lag})",
            context=context,
            reference_period=reference.raw,
            required_period=target.raw,
            lag=lag,
        )
    
    validate_positive_index(obs.value, context=context)
    return obs
