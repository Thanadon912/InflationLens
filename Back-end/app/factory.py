"""Flask application factory.

CALCULATION_ENGINE_GUIDELINES.md section 22 (Security): secrets stay in
backend environment variables and are never sent to the frontend or
logged; external payloads (here, request bodies) are validated before use
(``app.api.schemas``); network/file access from calculation workers is
limited (this API never lets a request body reach a network call -- there
are no provider adapters in this phase, see Back-end/README.md).
"""

from __future__ import annotations

import logging
import os

from flask import Flask
from flask_cors import CORS

from app.api.blueprint import calculate_bp
from app.api.data import data_bp
from app.api.errors import register_error_handlers
from app.api.meta import meta_bp
from app.data.cli import register_data_cli

# Reject request bodies above this size outright, before any JSON parsing
# or engine work happens (defense against oversized/malicious payloads).
MAX_CONTENT_LENGTH_BYTES = 2 * 1024 * 1024  # 2 MiB


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH_BYTES
    app.config["JSON_SORT_KEYS"] = False

    allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173")
    CORS(app, resources={r"/api/*": {"origins": [o.strip() for o in allowed_origins.split(",") if o.strip()]}})

    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
    # httpx logs full request URLs at INFO, which can include provider API
    # keys in query parameters. Provider failures are logged by our own
    # sanitized integration layer instead.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    app.register_blueprint(meta_bp, url_prefix="/api/v1")
    app.register_blueprint(calculate_bp, url_prefix="/api/v1")
    app.register_blueprint(data_bp, url_prefix="/api/v1")

    register_error_handlers(app)
    register_data_cli(app)

    return app
