"""Methodology versioning and input provenance.

CALCULATION_ENGINE_GUIDELINES.md section 25 requires every displayed value
to be traceable back through "calculation method -> methodology version ->
configuration version -> normalized observations -> provider series ->
raw provider response -> official source." ``InputProvenance`` carries the
provider/series half of that chain; ``MethodologyVersion`` enforces the
semantic-versioning rule from COUNTRY_INFLATION_METHODS.md section 19.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_SEMVER_RE = re.compile(r"^(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")


@dataclass(frozen=True)
class InputProvenance:
    """One entry in an ``IndicatorResult.input_series`` list.

    Mirrors the ``input_series`` items in ENGINE guidelines section 12:
    ``{"provider": "bls", "series_id": "CUUR0000SA0"}``.
    """

    provider: str
    series_id: str

    def to_dict(self) -> dict:
        return {"provider": self.provider, "series_id": self.series_id}


@dataclass(frozen=True, order=True)
class MethodologyVersion:
    """A semantic version identifying the exact formula/config revision
    used to produce a result.

    Ordering follows standard semver precedence (major, then minor, then
    patch) so that callers can detect whether a cached result was produced
    by an older methodology and needs to be invalidated, per ENGINE
    guidelines section 21 ("A methodology change must invalidate affected
    calculated results.").
    """

    major: int
    minor: int
    patch: int
    _raw: str

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self._raw

    @classmethod
    def parse(cls, raw: str) -> "MethodologyVersion":
        m = _SEMVER_RE.match(raw)
        if not m:
            raise ValueError(f"Methodology version must be semantic version 'X.Y.Z', got {raw!r}")
        return cls(major=int(m["major"]), minor=int(m["minor"]), patch=int(m["patch"]), _raw=raw)
