"""Read-only metadata endpoints.

Lets the frontend explain every displayed value (COUNTRY_INFLATION_METHODS.md
section 20's four required questions: what is measured, how, what it
captures, what it misses) without hard-coding indicator lists client-side.
"""

from __future__ import annotations

import hashlib

from flask import Blueprint, jsonify, request
from app.api.contracts import contract_metadata

from app.config.loader import (
    available_country_profiles,
    load_country_profile,
    load_global_weights,
    load_indicator_registry,
    load_methodology_versions,
)

meta_bp = Blueprint("meta", __name__)


@meta_bp.after_request
def _add_conditional_cache_headers(response):
    if request.method in ("GET", "HEAD") and response.status_code == 200:
        if request.path.endswith("/health"):
            response.headers.setdefault("Cache-Control", "no-cache")
            return response
        digest = hashlib.sha256(response.get_data()).hexdigest()[:32]
        response.set_etag(digest)
        response.headers.setdefault("Cache-Control", "public, max-age=300, must-revalidate")
        return response.make_conditional(request)
    return response


@meta_bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@meta_bp.get("/meta/indicators")
def indicators():
    registry = load_indicator_registry()
    payload = {
        **registry,
        "country": {
            indicator_id: {**definition, "api_contract": contract_metadata(indicator_id)}
            for indicator_id, definition in registry["country"].items()
        },
        "global": {
            indicator_id: {**definition, "api_contract": contract_metadata(indicator_id)}
            for indicator_id, definition in registry["global"].items()
        },
    }
    return jsonify(payload)


@meta_bp.get("/meta/methodology")
def methodology():
    return jsonify(load_methodology_versions())


@meta_bp.get("/meta/global-weights")
def global_weights():
    return jsonify(load_global_weights())


@meta_bp.get("/meta/countries")
def countries():
    return jsonify({"available": available_country_profiles()})


@meta_bp.get("/meta/config/country/<geography>")
def country_config(geography: str):
    profile = load_country_profile(geography)
    return jsonify(profile)
