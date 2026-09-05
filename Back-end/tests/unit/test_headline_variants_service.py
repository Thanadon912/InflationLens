"""Unit coverage for IngestionService's per-measure headline_consumer_inflation
path (app/data/service.py: _headline_variants / _calculate_headline_variants /
_save_published_rate), seeding observations directly rather than mocking HTTP
-- mirrors tests/integration/test_live_data_pipeline.py's
test_store_preserves_revisions_lineage_and_raw_hash in style.
"""

from __future__ import annotations

from app.data.service import IngestionService
from app.data.store import SnapshotStore
from app.providers.base import SourcePoint


def _mapping_for(registry, *, measure_id=None, region_id=None):
    for m in registry["sources"]:
        if m["geography"] == "USA" and m["indicator_id"] == "headline_consumer_inflation" and m["role"] == "all_items_cpi_index" and m.get("measure_id") == measure_id and m.get("region_id") == region_id:
            return m
    raise AssertionError(f"no USA headline_consumer_inflation mapping for measure_id={measure_id!r} region_id={region_id!r}")


def test_one_bad_measure_does_not_block_the_others(tmp_path):
    store = SnapshotStore(tmp_path / "variants.sqlite3")
    service = IngestionService(store)
    registry = service.registry

    run = store.create_run("USA", "headline_consumer_inflation")

    # ppi: a clean, computable pair of periods.
    ppi_mapping = _mapping_for(registry, measure_id="ppi")
    store.save_point(run, None, SourcePoint(ppi_mapping, "2025-07", 250.0))
    store.save_point(run, None, SourcePoint(ppi_mapping, "2026-07", 260.0))

    # cpi: a non-positive index value, which the engine's
    # validate_positive_index rejects -- this measure must fail without
    # taking ppi down with it.
    cpi_mapping = _mapping_for(registry, measure_id="cpi")
    store.save_point(run, None, SourcePoint(cpi_mapping, "2025-07", -1.0))
    store.save_point(run, None, SourcePoint(cpi_mapping, "2026-07", 333.9))

    calculated = service.calculate_available(run, "USA", "headline_consumer_inflation")
    assert calculated == 1  # only ppi

    ppi_result = store.get_result("USA", "headline_consumer_inflation", "2026-07", measure_id="ppi")
    assert ppi_result is not None
    assert round(ppi_result["result"]["value"], 1) == 4.0

    assert store.get_result("USA", "headline_consumer_inflation", "2026-07", measure_id="cpi") is None
    issues = store.issues(run)
    assert any(i["code"] == "PERIOD_UNAVAILABLE" and i["details"]["measure_id"] == "cpi" for i in issues)


def test_published_rate_measure_is_stored_without_recomputation(tmp_path):
    store = SnapshotStore(tmp_path / "trim.sqlite3")
    service = IngestionService(store)
    registry = service.registry

    run = store.create_run("USA", "headline_consumer_inflation")
    trim_mapping = _mapping_for(registry, measure_id="trim")
    assert trim_mapping.get("is_rate") is True
    store.save_point(run, None, SourcePoint(trim_mapping, "2026-06", 2.2, is_estimated=True))

    calculated = service.calculate_available(run, "USA", "headline_consumer_inflation")
    assert calculated >= 1

    result = store.get_result("USA", "headline_consumer_inflation", "2026-06", measure_id="trim")
    assert result is not None
    assert result["result"]["value"] == 2.2
    assert result["result"]["method"] == "published_rate"
    assert result["result"]["is_estimated"] is True
    assert result["result"]["confidence"] == "low"


def test_measure_with_no_observations_is_skipped_without_error(tmp_path):
    store = SnapshotStore(tmp_path / "empty.sqlite3")
    service = IngestionService(store)
    run = store.create_run("USA", "headline_consumer_inflation")
    assert service.calculate_available(run, "USA", "headline_consumer_inflation") == 0
    assert store.issues(run) == []
