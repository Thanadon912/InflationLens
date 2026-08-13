"""Confidence derivation and provenance collection shared by every engine.

CALCULATION_ENGINE_GUIDELINES.md section 14.1 defines confidence purely
from *how* a value was produced (official source, complete coverage, no
estimates, current data, validated metadata) — never from the value
itself (section 14.2: "Confidence must not change the numeric value").
This module gives every country/global engine module one consistent,
deterministic way to derive a :class:`Confidence` from the observations it
consumed, and one consistent way to build the ``input_series`` provenance
list required by section 12.
"""

from __future__ import annotations

from app.models.enums import Confidence, Coverage
from app.models.methodology import InputProvenance
from app.models.observation import Observation

_CONFIDENCE_RANK = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}


def derive_confidence(*observations: Observation) -> Confidence:
    """Derive an overall confidence level from the observations used.

    - Any estimated observation caps confidence at LOW (ENGINE guidelines
      section 14.1: "Low: estimated").
    - Any observation flagged with partial coverage caps confidence at
      MEDIUM.
    - Otherwise, the lowest explicit ``confidence`` any observation
      carries wins (a chain is only as strong as its weakest input); if no
      observation carries an explicit confidence, HIGH is assumed for
      validated, non-estimated, fully covered data.
    """

    if not observations:
        return Confidence.LOW
    if any(o.is_estimated for o in observations):
        return Confidence.LOW
    if any(o.coverage_status == Coverage.PARTIAL for o in observations):
        return Confidence.MEDIUM
    explicit = [o.confidence for o in observations if o.confidence is not None]
    if explicit:
        return min(explicit, key=lambda c: _CONFIDENCE_RANK[c])
    return Confidence.HIGH


def any_estimated(*observations: Observation) -> bool:
    return any(o.is_estimated for o in observations)


def build_provenance(*observations: Observation) -> tuple[InputProvenance, ...]:
    """Build a de-duplicated, order-preserving provenance tuple.

    Mirrors ENGINE guidelines section 12's ``input_series`` list:
    ``[{"provider": "bls", "series_id": "CUUR0000SA0"}]``.
    """

    seen: set[tuple[str, str]] = set()
    result: list[InputProvenance] = []
    for obs in observations:
        key = (obs.provider, obs.source_series_id)
        if key not in seen:
            seen.add(key)
            result.append(InputProvenance(provider=obs.provider, series_id=obs.source_series_id))
    return tuple(result)


def gap_warnings(series, *, context: str) -> list[str]:
    """Return a warning list disclosing any gaps in ``series``.

    COUNTRY guidelines section 8.1 validation rule: "periods must be
    continuous or gaps disclosed." An empty list means no gaps.
    """

    gaps = series.gaps()
    if not gaps:
        return []
    gap_list = ", ".join(g.raw for g in gaps)
    return [f"{context}: series has gaps at periods [{gap_list}]"]
