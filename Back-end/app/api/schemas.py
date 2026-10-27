"""Request body parsing for the calculation API.

Translates raw JSON into the typed values the engine layer expects.
CALCULATION_ENGINE_GUIDELINES.md section 4 defines the normalized
observation contract as the engine's only allowed input shape; this
module is the boundary where that contract is enforced before anything
reaches ``app.engines.*``. Parsing errors raise :class:`SchemaError`,
mapped by ``app.api.errors`` to HTTP 400 -- distinct from the domain
``EngineError`` subclasses (mapped to 422), so a malformed request and a
well-formed-but-uncalculable request are never confused.
"""

from __future__ import annotations

from collections.abc import Mapping

from app.engines.shared.errors import EngineError, SeriesDefinitionError
from app.engines.shared.periods import Period, parse_period
from app.models.enums import Confidence, Coverage, Frequency, Unit, ValidationStatus
from app.models.observation import Observation
from app.models.series import ObservationSeries


class SchemaError(ValueError):
    """Raised when a request body is missing a required field or has the
    wrong shape/type. Distinct from ``EngineError``: this is a client
    request-format problem, not a calculation-domain failure."""

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


def require(body: Mapping, field: str) -> object:
    if field not in body or body[field] is None:
        raise SchemaError(f"Missing required field: {field!r}", field=field)
    return body[field]


def get_float(body: Mapping, field: str, *, required: bool = True, default: float | None = None) -> float | None:
    if field not in body or body[field] is None:
        if required:
            raise SchemaError(f"Missing required numeric field: {field!r}", field=field)
        return default
    value = body[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaError(f"Field {field!r} must be numeric, got {type(value).__name__}", field=field)
    return float(value)


def get_str(body: Mapping, field: str, *, required: bool = True, default: str | None = None) -> str | None:
    if field not in body or body[field] is None:
        if required:
            raise SchemaError(f"Missing required string field: {field!r}", field=field)
        return default
    value = body[field]
    if not isinstance(value, str):
        raise SchemaError(f"Field {field!r} must be a string, got {type(value).__name__}", field=field)
    return value


def get_mapping(body: Mapping, field: str, *, required: bool = True) -> dict[str, float] | None:
    if field not in body or body[field] is None:
        if required:
            raise SchemaError(f"Missing required object field: {field!r}", field=field)
        return None
    value = body[field]
    if not isinstance(value, dict):
        raise SchemaError(f"Field {field!r} must be an object, got {type(value).__name__}", field=field)
    result = {}
    for k, v in value.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise SchemaError(f"Field {field!r}[{k!r}] must be numeric", field=field, key=k)
        result[k] = float(v)
    return result


def parse_period_field(body: Mapping, field: str, frequency: Frequency) -> Period:
    raw = get_str(body, field)
    try:
        return parse_period(raw, frequency)
    except SeriesDefinitionError as exc:
        raise SchemaError(str(exc), field=field, value=raw) from exc


def _parse_enum(value: object, enum_cls, *, field: str):
    try:
        return enum_cls(value)
    except ValueError as exc:
        allowed = ", ".join(m.value for m in enum_cls)
        raise SchemaError(f"Field {field!r} must be one of [{allowed}], got {value!r}", field=field) from exc


def parse_observation(raw: Mapping) -> Observation:
    """Parse one normalized-observation JSON object (ENGINE guidelines
    section 4) into an :class:`Observation`."""

    if not isinstance(raw, Mapping):
        raise SchemaError("Each observation must be a JSON object")
    try:
        return Observation(
            provider=str(require(raw, "provider")),
            source_series_id=str(require(raw, "source_series_id")),
            indicator_id=str(require(raw, "indicator_id")),
            geography=str(require(raw, "geography")),
            frequency=_parse_enum(require(raw, "frequency"), Frequency, field="frequency"),
            unit=_parse_enum(require(raw, "unit"), Unit, field="unit"),
            observation_period=str(require(raw, "observation_period")),
            value=get_float(raw, "value"),
            retrieved_at=str(require(raw, "retrieved_at")),
            validation_status=_parse_enum(
                require(raw, "validation_status"), ValidationStatus, field="validation_status"
            ),
            publication_date=raw.get("publication_date"),
            seasonally_adjusted=raw.get("seasonally_adjusted"),
            source_url=raw.get("source_url"),
            is_estimated=bool(raw.get("is_estimated", False)),
            is_revised=bool(raw.get("is_revised", False)),
            data_vintage=raw.get("data_vintage"),
            methodology_version=raw.get("methodology_version"),
            confidence=_parse_enum(raw["confidence"], Confidence, field="confidence") if raw.get("confidence") else None,
            coverage_status=_parse_enum(raw["coverage_status"], Coverage, field="coverage_status") if raw.get("coverage_status") else None,
            component_id=get_str(raw, "component_id", required=False),
            currency=get_str(raw, "currency", required=False),
        )
    except SchemaError:
        raise
    except EngineError:
        raise
    except Exception as exc:  # noqa: BLE001 - re-raised as a schema error with context
        raise SchemaError(f"Invalid observation: {exc}") from exc


def parse_observation_series(raw: object, *, field: str = "observations") -> ObservationSeries:
    if not isinstance(raw, list) or not raw:
        raise SchemaError(f"Field {field!r} must be a non-empty array of observations", field=field)
    observations = [parse_observation(o) for o in raw]
    try:
        return ObservationSeries(observations)
    except SeriesDefinitionError as exc:
        raise SchemaError(str(exc), field=field) from exc


def normalize_string_sequence(val: object) -> tuple[str, ...]:
    """turn input into a tuple of string
    - None หรือ "" -> ()
    - "food" -> ("food",)
    - ["food", "energy"] -> ("food", "energy")
    """

    if val is None:
        return ()

    if isinstance(val, str):
        clean_str = val.strip()
        return (clean_str,) if clean_str else ()

    if isinstance(val, (list, tuple)):
        return tuple(str(x).strip() for x in val if x and str(x).strip())

    return ()