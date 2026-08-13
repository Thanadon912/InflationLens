"""Small API-layer utilities: timestamps and provenance helpers.

Timestamps are generated at the edge (the API layer), not inside engine
functions, so the calculation engine itself stays a pure, deterministic
function of its inputs (CALCULATION_ENGINE_GUIDELINES.md section 2).
"""

from __future__ import annotations

from datetime import UTC, datetime


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
