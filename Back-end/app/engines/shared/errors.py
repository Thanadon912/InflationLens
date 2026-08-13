"""Domain errors for the calculation engine.

CALCULATION_ENGINE_GUIDELINES.md section 13 requires explicit domain errors
and states plainly: "Do not return zero when calculation fails." Every error
here carries a machine-readable ``code`` and a ``details`` dict so the API
layer (see app/api/errors.py) can translate it into a structured HTTP
response without inventing new semantics, and so audit logs (section 20)
can record exactly what went wrong.
"""

from __future__ import annotations


class EngineError(Exception):
    """Base class for all deterministic-engine domain errors.

    Subclasses set ``code`` (a stable machine-readable identifier used in
    API responses and logs) and populate ``details`` with structured
    context. ``message`` is the human-readable summary.
    """

    code: str = "ENGINE_ERROR"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message, "details": self.details}


class UnitMismatchError(EngineError):
    """Raised when an input's unit does not match what a formula accepts.

    ENGINE guidelines section 5.2: "If the input uses percent_yoy, the
    engine must reject it unless the formula explicitly accepts rates."
    """

    code = "UNIT_MISMATCH"

    def __init__(self, expected: str, received: str, indicator: str) -> None:
        super().__init__(
            f"Expected unit {expected!r} but received {received!r} for indicator {indicator!r}",
            expected=expected,
            received=received,
            indicator=indicator,
        )


class FrequencyMismatchError(EngineError):
    """Raised when input frequency does not match what a formula requires,
    or when series of incompatible frequencies are combined without an
    explicit alignment policy (ENGINE guidelines section 6.3)."""

    code = "FREQUENCY_MISMATCH"

    def __init__(self, expected: str, received: str, indicator: str) -> None:
        super().__init__(
            f"Expected frequency {expected!r} but received {received!r} for indicator {indicator!r}",
            expected=expected,
            received=received,
            indicator=indicator,
        )


class PeriodAlignmentError(EngineError):
    """Raised when inputs refer to different economic periods without an
    explicit, documented lag (ENGINE guidelines section 6.4)."""

    code = "PERIOD_ALIGNMENT"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message, **details)


class InsufficientHistoryError(EngineError):
    """Raised when a series lacks enough history for the requested lag
    (e.g. year-over-year growth needs an observation 12 months back)."""

    code = "INSUFFICIENT_HISTORY"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message, **details)


class InvalidWeightError(EngineError):
    """Raised when weights are negative, empty, or do not sum to one
    within tolerance (ENGINE guidelines section 7.5, 11)."""

    code = "INVALID_WEIGHT"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message, **details)


class CoverageThresholdError(EngineError):
    """Raised when available coverage falls below a configured minimum
    threshold and renormalization is therefore not permitted (ENGINE
    guidelines section 10.3, 10.4)."""

    code = "COVERAGE_THRESHOLD"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message, **details)


class MissingRequiredInputError(EngineError):
    """Raised when a required input for an indicator is absent. Missing
    data must remain missing (ENGINE guidelines section 10.1) rather than
    being silently substituted."""

    code = "MISSING_REQUIRED_INPUT"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message, **details)


class UnsupportedMethodError(EngineError):
    """Raised when a requested calculation method/frequency/aggregation is
    not implemented or not defined by the methodology documents."""

    code = "UNSUPPORTED_METHOD"

    def __init__(self, method: str, context: str = "") -> None:
        message = f"Unsupported method {method!r}"
        if context:
            message += f" ({context})"
        super().__init__(message, method=method, context=context)


class SeriesDefinitionError(EngineError):
    """Raised when an observation or series is malformed: unparsable
    period, duplicate periods, non-monotonic ordering, etc."""

    code = "SERIES_DEFINITION"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message, **details)


class DataQualityError(EngineError):
    """Raised for values that fail basic sanity checks required by the
    methodology, e.g. a zero or negative index level (ENGINE guidelines
    section 8.1: "no zero or negative index values")."""

    code = "DATA_QUALITY"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message, **details)
