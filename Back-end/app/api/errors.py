"""Structured error handling for the API.

CALCULATION_ENGINE_GUIDELINES.md section 13: "Do not return zero when
calculation fails." This module ensures every failure mode -- a malformed
request, a domain calculation error, a missing indicator, or a server
misconfiguration -- returns a structured JSON error instead of a
fabricated result, and never leaks secrets (section 22: "Do not log
secrets.").
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from app.api.schemas import SchemaError
from app.config.loader import ConfigError
from app.engines.shared.errors import EngineError

logger = logging.getLogger("inflation_engine.api")


class IndicatorNotFoundError(Exception):
    def __init__(self, indicator_id: str, scope: str) -> None:
        super().__init__(f"Unknown {scope} indicator: {indicator_id!r}")
        self.indicator_id = indicator_id
        self.scope = scope


def _error_response(status: int, code: str, message: str, details: dict | None = None):
    return jsonify({"error": {"code": code, "message": message, "details": details or {}}}), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(SchemaError)
    def handle_schema_error(exc: SchemaError):
        return _error_response(400, "SCHEMA_ERROR", exc.message, exc.details)

    @app.errorhandler(EngineError)
    def handle_engine_error(exc: EngineError):
        # ENGINE guidelines section 13: calculation failures are explicit
        # domain errors, never a silent zero. 422 = well-formed request,
        # cannot be processed by the calculation domain.
        return _error_response(422, exc.code, exc.message, exc.details)

    @app.errorhandler(IndicatorNotFoundError)
    def handle_indicator_not_found(exc: IndicatorNotFoundError):
        return _error_response(404, "INDICATOR_NOT_FOUND", str(exc), {"indicator_id": exc.indicator_id, "scope": exc.scope})

    @app.errorhandler(ConfigError)
    def handle_config_error(exc: ConfigError):
        if str(exc).startswith("No country profile configured"):
            return _error_response(404, "GEOGRAPHY_NOT_FOUND", str(exc), {})
        logger.error("Configuration error: %s", exc)
        return _error_response(500, "CONFIG_ERROR", "Server configuration error", {})

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        return _error_response(exc.code or 500, f"HTTP_{exc.code}", exc.description or exc.name, {})

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        # Never echo internal exception details (may include payload
        # fragments) back to the client; log server-side only.
        logger.exception("Unhandled error")
        return _error_response(500, "INTERNAL_ERROR", "An unexpected error occurred", {})
