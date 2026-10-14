"""HTTP routes for indicator calculation.

Two request shapes:

- ``POST /country/<geo>/<indicator_id>`` / ``POST /global/<indicator_id>``:
  body is that one indicator's own fields (see ``app.api.country``/
  ``app.api.global_`` for what each handler reads). A calculation failure
  here is a hard error (422/400) -- this endpoint is for a caller who
  wants one specific, fully-available number.
- ``POST /country/<geo>/dashboard`` / ``POST /global/dashboard``: body is
  ``{"<indicator_id>": {...that indicator's own fields...}, ...}``.
  Indicators omitted from the body, or whose calculation fails, are
  reported as ``unavailable`` (ENGINE guidelines section 10.1: missing
  data stays missing) instead of failing the whole request -- so the
  dashboard always returns everything it *can* compute.
"""

from __future__ import annotations

from dataclasses import replace

from flask import Blueprint, jsonify, request

from app.api import country as country_handlers
from app.api import global_ as global_handlers
from app.api.audit import log_calculation
from app.api.contracts import normalize_request
from app.api.errors import IndicatorNotFoundError
from app.api.schemas import SchemaError
from app.api.util import now_iso
from app.config.loader import load_country_profile, load_global_weights, load_methodology_versions
from app.engines.shared.errors import CoverageThresholdError, EngineError
from app.models.indicator_result import IndicatorResult

calculate_bp = Blueprint("calculate", __name__)


def _get_json_body() -> dict:
    body = request.get_json(silent=True)
    if body is None:
        raise SchemaError("Request body must be valid JSON")
    if not isinstance(body, dict):
        raise SchemaError("Request body must be a JSON object")
    return body


@calculate_bp.post("/country/<geography>/<indicator_id>")
def calculate_country_indicator(geography: str, indicator_id: str):
    handler = country_handlers.HANDLERS.get(indicator_id)
    if handler is None:
        raise IndicatorNotFoundError(indicator_id, scope="country")
    profile = load_country_profile(geography)
    body = _get_json_body()
    result = _calculate_country(handler, geography.upper(), indicator_id, body, profile)
    log_calculation(result)
    return jsonify(result.to_dict())


@calculate_bp.post("/country/<geography>/dashboard")
def calculate_country_dashboard(geography: str):
    profile = load_country_profile(geography)
    body = _get_json_body()
    versions = load_methodology_versions()["country"]
    results = []
    for indicator_id, handler in country_handlers.HANDLERS.items():
        sub_body = body.get(indicator_id)
        results.append(
            _safe_call(
                lambda h=handler, b=sub_body, i=indicator_id: _calculate_country(h, geography.upper(), i, b or {}, profile),
                indicator_id=indicator_id,
                geography=geography.upper(),
                methodology_version=versions.get(indicator_id, "1.0.0"),
                requested=sub_body is not None,
            )
        )
    for result in results:
        log_calculation(result)
    return jsonify({"geography": geography.upper(), "indicators": [r.to_dict() for r in results]})


@calculate_bp.post("/global/<indicator_id>")
def calculate_global_indicator(indicator_id: str):
    handler = global_handlers.HANDLERS.get(indicator_id)
    if handler is None:
        raise IndicatorNotFoundError(indicator_id, scope="global")
    global_cfg = load_global_weights()
    body = _get_json_body()
    result = _calculate_global(handler, indicator_id, body, global_cfg)
    log_calculation(result)
    return jsonify(result.to_dict())


@calculate_bp.post("/global/dashboard")
def calculate_global_dashboard():
    global_cfg = load_global_weights()
    body = _get_json_body()
    versions = load_methodology_versions()["global"]
    results = []
    for indicator_id, handler in global_handlers.HANDLERS.items():
        sub_body = body.get(indicator_id)
        results.append(
            _safe_call(
                lambda h=handler, b=sub_body, i=indicator_id: _calculate_global(h, i, b or {}, global_cfg),
                indicator_id=indicator_id,
                geography="GLOBAL",
                methodology_version=versions.get(indicator_id, "1.0.0"),
                requested=sub_body is not None,
            )
        )
    for result in results:
        log_calculation(result)
    return jsonify({"geography": "GLOBAL", "indicators": [r.to_dict() for r in results]})


def _safe_call(fn, *, indicator_id: str, geography: str, methodology_version: str, requested: bool) -> IndicatorResult:
    if not requested:
        return IndicatorResult.unavailable(
            indicator_id=indicator_id,
            geography=geography,
            period="",
            method="unavailable",
            methodology_version=methodology_version,
            calculated_at=now_iso(),
            reason="not requested: no input body supplied for this indicator",
        )
    try:
        return fn()
    except (EngineError, SchemaError, KeyError) as exc:
        message = exc.message if hasattr(exc, "message") else str(exc)
        return IndicatorResult.unavailable(
            indicator_id=indicator_id,
            geography=geography,
            period="",
            method="unavailable",
            methodology_version=methodology_version,
            calculated_at=now_iso(),
            reason=f"calculation failed: {message}"
        )


def _calculate_country(handler, geography: str, indicator_id: str, body: dict, profile: dict) -> IndicatorResult:
    normalized = normalize_request(indicator_id, body)
    result = handler(geography, normalized.legacy, profile)
    versions = load_methodology_versions()
    return _enrich_result(result, normalized, methodology_version=versions["country"][indicator_id], config_version=profile["profile_version"])


def _calculate_global(handler, indicator_id: str, body: dict, global_cfg: dict) -> IndicatorResult:
    normalized = normalize_request(
        indicator_id,
        body,
        global_scope=True,
        structurally_dominant_weight=global_cfg["coverage_thresholds"]["structurally_dominant_missing_weight"],
    )
    result = handler(normalized.legacy, global_cfg)
    _enforce_global_coverage(result, global_cfg)
    versions = load_methodology_versions()
    return _enrich_result(result, normalized, methodology_version=versions["global"][indicator_id], config_version=global_cfg["config_version"])


def _enforce_global_coverage(result: IndicatorResult, global_cfg: dict) -> None:
    report = result.coverage_report
    if report is None:
        raise CoverageThresholdError("Global result is missing its required coverage report")
    thresholds = global_cfg["coverage_thresholds"]
    checks = (
        ("population", report.population_coverage_percent, thresholds["population_minimum_percent"]),
        ("gdp_ppp", report.gdp_ppp_coverage_percent, thresholds["gdp_ppp_minimum_percent"]),
        ("consumption_ppp", report.consumption_ppp_coverage_percent, thresholds["consumption_ppp_minimum_percent"]),
    )
    for basis, value, minimum in checks:
        if value is None or value < minimum:
            raise CoverageThresholdError(
                f"{result.indicator_id}: {basis} coverage does not meet the configured threshold",
                basis=basis,
                coverage_percent=value,
                threshold_percent=minimum,
            )


def _enrich_result(result: IndicatorResult, normalized, *, methodology_version: str, config_version: str) -> IndicatorResult:
    rank = {"low": 0, "medium": 1, "high": 2}
    confidence = min((result.confidence, normalized.confidence), key=lambda c: rank[c.value])
    coverage_report = result.coverage_report
    if coverage_report is not None and normalized.original_weights is not None:
        coverage_report = replace(
            coverage_report,
            original_weights=dict(normalized.original_weights),
            adjusted_weights=dict(normalized.adjusted_weights or {}),
            weights_renormalized=dict(normalized.original_weights) != dict(normalized.adjusted_weights or {}),
        )
    return replace(
        result,
        methodology_version=methodology_version,
        config_version=config_version,
        input_series=normalized.input_series,
        confidence=confidence,
        is_estimated=result.is_estimated or any(o.is_estimated for o in normalized.observations),
        coverage_report=coverage_report,
    )
