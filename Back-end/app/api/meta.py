"""Read-only metadata endpoints.

Lets the frontend explain every displayed value (COUNTRY_INFLATION_METHODS.md
section 20's four required questions: what is measured, how, what it
captures, what it misses) without hard-coding indicator lists client-side.
"""

from __future__ import annotations

from flask import Blueprint, jsonify

from app.config.loader import (
    available_country_profiles,
    load_country_profile,
    load_global_weights,
    load_indicator_registry,
    load_methodology_versions,
)

meta_bp = Blueprint("meta", __name__)


@meta_bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@meta_bp.get("/meta/indicators")
def indicators():
    return jsonify(load_indicator_registry())


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
