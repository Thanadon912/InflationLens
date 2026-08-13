from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.config.loader import load_source_registry
from app.data.service import SUPPORTED_INDICATORS, decorate_snapshot
from app.data.store import SnapshotStore

data_bp = Blueprint("data", __name__)


def _not_found(message: str):
    return jsonify({"error": {"code": "DATA_SNAPSHOT_NOT_FOUND", "message": message, "details": {}}}), 404


@data_bp.get("/country/<geography>/<indicator_id>")
def cached_country_indicator(geography: str, indicator_id: str):
    if indicator_id not in SUPPORTED_INDICATORS:
        return _not_found(f"No cached-provider integration is configured for {indicator_id!r}")
    period = request.args.get("period", "latest")
    row = SnapshotStore().get_result(geography.upper(), indicator_id, period)
    if row is None:
        return _not_found(f"No data snapshot for {geography.upper()}/{indicator_id}/{period}")
    return jsonify(decorate_snapshot(row, load_source_registry()["defaults"]))


@data_bp.get("/country/<geography>/dashboard")
def cached_country_dashboard(geography: str):
    period = request.args.get("period", "latest")
    store = SnapshotStore()
    defaults = load_source_registry()["defaults"]
    results = []
    for indicator_id in SUPPORTED_INDICATORS:
        row = store.get_result(geography.upper(), indicator_id, period)
        if row:
            results.append(decorate_snapshot(row, defaults))
        else:
            results.append({"indicator_id": indicator_id, "geography": geography.upper(), "period": period, "value": None, "coverage": "unavailable", "confidence": "low", "warnings": ["No cached provider snapshot is available"]})
    return jsonify({"geography": geography.upper(), "requested_period": period, "indicators": results})


@data_bp.get("/data/status")
def data_status():
    return jsonify(SnapshotStore().status())


@data_bp.get("/data/issues")
def data_issues():
    return jsonify({"issues": SnapshotStore().issues(request.args.get("run_id"))})


@data_bp.get("/data/lineage/<snapshot_id>")
def data_lineage(snapshot_id: str):
    lineage = SnapshotStore().lineage(snapshot_id)
    return jsonify(lineage) if lineage else _not_found(f"Unknown snapshot {snapshot_id}")


@data_bp.get("/meta/data-sources")
def data_sources():
    registry = load_source_registry()
    public_sources = [{k: v for k, v in item.items() if k not in {"source_url"}} for item in registry["sources"]]
    return jsonify({"config_version": registry["config_version"], "defaults": registry["defaults"], "sources": public_sources})
