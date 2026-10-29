import sqlite3

import pytest

from app.data.store import CorruptCacheError, SnapshotStore
from app.providers.base import FetchBundle, SourcePoint


def _seed_result(store: SnapshotStore, run_id: str, geography: str, indicator_id: str, period: str, *, measure_id=None, region_id=None, value=3.0):
    store.save_result(
        run_id,
        geography,
        indicator_id,
        period,
        {"calculated_at": "2026-08-01T00:00:00Z", "methodology_version": "1.0.1", "config_version": "1.0.0", "value": value},
        ["2026-08-01"],
        measure_id=measure_id,
        region_id=region_id,
    )


def test_relative_db_path_resolves_against_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    store = SnapshotStore("relative.sqlite3")
    assert store.path.is_absolute()
    assert store.path == tmp_path / "relative.sqlite3"


def test_migrates_pre_measure_schema_preserving_rows(tmp_path):
    db_path = tmp_path / "legacy.sqlite3"
    # Build the database exactly as it looked before the measure_id/region_id
    # dimension existed: indicator_results has no such columns and is bound
    # by the old single-series UNIQUE constraint.
    legacy = sqlite3.connect(db_path)
    legacy.executescript(
        """
        CREATE TABLE sync_runs (
          id TEXT PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT,
          status TEXT NOT NULL, requested_geography TEXT NOT NULL,
          requested_indicator TEXT NOT NULL, successes INTEGER NOT NULL DEFAULT 0,
          failures INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE indicator_results (
          id TEXT PRIMARY KEY, sync_run_id TEXT NOT NULL REFERENCES sync_runs(id),
          geography TEXT NOT NULL, indicator_id TEXT NOT NULL, period TEXT NOT NULL,
          calculated_at TEXT NOT NULL, methodology_version TEXT NOT NULL,
          config_version TEXT, source_vintages TEXT NOT NULL, result_json TEXT NOT NULL,
          UNIQUE(sync_run_id, geography, indicator_id, period)
        );
        INSERT INTO sync_runs VALUES('run-1','2026-01-01T00:00:00Z','2026-01-01T00:00:01Z','success','USA','all',1,0);
        INSERT INTO indicator_results VALUES('snap-1','run-1','USA','headline_consumer_inflation','2026-07','2026-08-01T00:00:00Z','1.0.1','1.0.0','[]','{"value": 3.4}');
        """
    )
    legacy.commit()
    legacy.close()

    store = SnapshotStore(db_path)  # triggers _migrate_indicator_results on open

    with store.connect() as db:
        columns = {row["name"] for row in db.execute("PRAGMA table_info(indicator_results)")}
    assert {"measure_id", "region_id"}.issubset(columns)

    # The migrated row keeps its pre-measure identity (measure_id=NULL);
    # get_result's own "default to cpi" convenience does not apply here
    # since the caller is asking for the NULL row specifically, so
    # list_latest_results (which never guesses a default) is what proves
    # the migration preserved it rather than silently dropping it.
    preserved = store.list_latest_results("USA", "headline_consumer_inflation", measure_id=None, region_id=None)
    assert len(preserved) == 1
    assert preserved[0]["result"]["value"] == 3.4

    # Re-opening an already-migrated database is a no-op (idempotent).
    SnapshotStore(db_path)
    with store.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM indicator_results").fetchone()[0] == 1

    # The rebuilt table enforces the new, wider uniqueness -- a second
    # measure for the same run/geography/indicator/period is not rejected.
    store2 = SnapshotStore(db_path)
    _seed_result(store2, "run-1", "USA", "headline_consumer_inflation", "2026-07", measure_id="core", value=2.5)
    assert store2.get_result("USA", "headline_consumer_inflation", "2026-07", measure_id="core")["result"]["value"] == 2.5


def test_get_result_defaults_headline_to_cpi_measure(tmp_path):
    store = SnapshotStore(tmp_path / "measures.sqlite3")
    run = store.create_run("USA", "headline_consumer_inflation")
    _seed_result(store, run, "USA", "headline_consumer_inflation", "2026-07", measure_id="cpi", value=3.4)
    _seed_result(store, run, "USA", "headline_consumer_inflation", "2026-07", measure_id="core", value=2.5)

    # No measure_id given -> the primary CPI-U series, preserving the
    # pre-measures behavior of the two-argument call.
    assert store.get_result("USA", "headline_consumer_inflation")["result"]["value"] == 3.4
    assert store.get_result("USA", "headline_consumer_inflation", measure_id="core")["result"]["value"] == 2.5
    assert store.get_result("USA", "headline_consumer_inflation", measure_id="missing") is None


def test_list_latest_results_one_row_per_variant_at_its_own_latest_period(tmp_path):
    store = SnapshotStore(tmp_path / "variants.sqlite3")
    run = store.create_run("USA", "headline_consumer_inflation")
    _seed_result(store, run, "USA", "headline_consumer_inflation", "2026-06", measure_id="cpi", value=3.3)
    _seed_result(store, run, "USA", "headline_consumer_inflation", "2026-07", measure_id="cpi", value=3.4)
    _seed_result(store, run, "USA", "headline_consumer_inflation", "2026-06", measure_id="core", value=2.4)
    _seed_result(store, run, "USA", "headline_consumer_inflation", "2026-07", measure_id="cpi", region_id="South", value=3.6)

    national = store.list_latest_results("USA", "headline_consumer_inflation", region_id=None)
    by_measure = {row["measure_id"]: row["result"]["value"] for row in national}
    assert by_measure == {"cpi": 3.4, "core": 2.4}

    regional = store.list_latest_results("USA", "headline_consumer_inflation", measure_id="cpi", region_id="South")
    assert len(regional) == 1
    assert regional[0]["result"]["value"] == 3.6

    everything = store.list_latest_results("USA", "headline_consumer_inflation")
    assert len(everything) == 3


def test_latest_by_component_picks_each_countrys_newest_year(tmp_path):
    store = SnapshotStore(tmp_path / "cross-section.sqlite3")
    run = store.create_run("GLOBAL", "median_country_inflation")
    mapping = {"provider": "world_bank", "series_id": "FP.CPI.TOTL.ZG", "indicator_id": "median_country_inflation", "role": "country_rates", "geography": "GLOBAL", "component_id": "USA", "frequency": "annual", "unit": "percent_yoy"}
    store.save_point(run, None, SourcePoint(mapping, "2023", 4.1))
    store.save_point(run, None, SourcePoint(mapping, "2024", 3.0))
    other = {**mapping, "component_id": "FRA"}
    store.save_point(run, None, SourcePoint(other, "2024", 2.4))

    rows = store.latest_by_component("GLOBAL", "median_country_inflation", "country_rates")
    by_country = {row["component_id"]: row["value"] for row in rows}
    assert by_country == {"USA": 3.0, "FRA": 2.4}


def test_save_bundle_and_point_without_raw_response(tmp_path):
    store = SnapshotStore(tmp_path / "bundle.sqlite3")
    run = store.create_run("USA", "headline_consumer_inflation")
    mapping = {"provider": "test", "series_id": "S", "indicator_id": "i", "role": "r", "geography": "USA", "frequency": "monthly", "unit": "index"}
    bundle = FetchBundle("test", "https://example.test", "2026-01-01T00:00:00Z", b"raw", "application/json", ())
    raw_id = store.save_bundle(run, bundle)
    obs_id = store.save_point(run, raw_id, SourcePoint(mapping, "2026-01", 100.0))
    assert obs_id


def test_busy_timeout_pragma_is_set_on_every_connection(tmp_path):
    # Every call opens its own connection (see connect()'s docstring); a
    # busy_timeout is what keeps a concurrent `data sync` from surfacing a
    # raw "database is locked" OperationalError on first contention.
    store = SnapshotStore(tmp_path / "timeout.sqlite3")
    with store.connect() as db:
        assert db.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


class TestCorruptCache:
    def test_corrupt_result_json_raises_corrupt_cache_error_not_bare_json_error(self, tmp_path):
        store = SnapshotStore(tmp_path / "corrupt.sqlite3")
        run = store.create_run("USA", "headline_consumer_inflation")
        _seed_result(store, run, "USA", "headline_consumer_inflation", "2026-07", measure_id="cpi", value=3.4)
        with store.connect() as db:
            db.execute("UPDATE indicator_results SET result_json = ? WHERE geography='USA'", ("{not valid json",))

        with pytest.raises(CorruptCacheError):
            store.get_result("USA", "headline_consumer_inflation", "2026-07", measure_id="cpi")

    def test_corrupt_result_json_in_list_latest_results_raises_corrupt_cache_error(self, tmp_path):
        store = SnapshotStore(tmp_path / "corrupt-list.sqlite3")
        run = store.create_run("USA", "headline_consumer_inflation")
        _seed_result(store, run, "USA", "headline_consumer_inflation", "2026-07", measure_id="cpi", value=3.4)
        with store.connect() as db:
            db.execute("UPDATE indicator_results SET source_vintages = ? WHERE geography='USA'", ("not json at all",))

        with pytest.raises(CorruptCacheError):
            store.list_latest_results("USA", "headline_consumer_inflation")

    def test_corrupt_details_json_in_issues_raises_corrupt_cache_error(self, tmp_path):
        store = SnapshotStore(tmp_path / "corrupt-issues.sqlite3")
        run = store.create_run("USA", "headline_consumer_inflation")
        store.add_issue(run, "PROVIDER_FETCH_FAILED", "boom", provider="bls")
        with store.connect() as db:
            db.execute("UPDATE sync_issues SET details_json = ?", ("{broken",))

        with pytest.raises(CorruptCacheError):
            store.issues()


def test_version_aware_cache_filters_methodology_and_config_versions(tmp_path):
    store = SnapshotStore(tmp_path / "versions.sqlite3")
    run = store.create_run("USA", "headline_consumer_inflation")
    store.save_result(
        run,
        "USA",
        "headline_consumer_inflation",
        "2026-06",
        {"calculated_at": "2026-07-01T00:00:00Z", "methodology_version": "1.0.1", "config_version": "1.0.0", "value": 2.9},
        ["2026-07-01"],
        measure_id="cpi",
    )
    store.save_result(
        run,
        "USA",
        "headline_consumer_inflation",
        "2026-07",
        {"calculated_at": "2026-08-01T00:00:00Z", "methodology_version": "1.0.1", "config_version": "1.0.0", "value": 3.4},
        ["2026-08-01"],
        measure_id="cpi",
    )

    assert store.get_result("USA", "headline_consumer_inflation", methodology_version="1.0.2") is None
    assert store.get_result("USA", "headline_consumer_inflation", methodology_version="1.0.1", config_version="1.0.0")["result"]["value"] == 3.4
    assert store.get_result("USA", "headline_consumer_inflation", methodology_version="1.0.1", config_version="2.0.0") is None

    assert store.list_latest_results("USA", "headline_consumer_inflation", methodology_version="1.0.2") == []
    latest_v101 = store.list_latest_results("USA", "headline_consumer_inflation", methodology_version="1.0.1", config_version="1.0.0")
    assert len(latest_v101) == 1
    assert latest_v101[0]["result"]["value"] == 3.4


def test_read_cache_immutability_invalidation_and_lru_eviction(tmp_path, monkeypatch):
    import app.data.store as store_mod

    store = SnapshotStore(tmp_path / "read-cache.sqlite3")
    run = store.create_run("USA", "headline_consumer_inflation")
    _seed_result(store, run, "USA", "headline_consumer_inflation", "2026-07", measure_id="cpi", value=3.4)

    first = store.get_result("USA", "headline_consumer_inflation", "2026-07", measure_id="cpi")
    first["result"]["value"] = 999.0  # caller mutates returned dict
    second = store.get_result("USA", "headline_consumer_inflation", "2026-07", measure_id="cpi")
    assert second["result"]["value"] == 3.4  # cached copy is uncorrupted

    # Repeated calls hit the in-memory read cache for list_latest_results, latest_observations, and latest_by_component
    assert len(store.list_latest_results("USA", "headline_consumer_inflation")) == 1
    assert len(store.list_latest_results("USA", "headline_consumer_inflation")) == 1

    mapping = {"provider": "world_bank", "series_id": "FP.CPI.TOTL.ZG", "indicator_id": "median_country_inflation", "role": "country_rates", "geography": "GLOBAL", "component_id": "USA", "frequency": "annual", "unit": "percent_yoy"}
    store.save_point(run, None, SourcePoint(mapping, "2024", 3.0))
    assert len(store.latest_observations("GLOBAL", "median_country_inflation", "country_rates")) == 1
    assert len(store.latest_observations("GLOBAL", "median_country_inflation", "country_rates")) == 1
    assert len(store.latest_by_component("GLOBAL", "median_country_inflation", "country_rates")) == 1
    assert len(store.latest_by_component("GLOBAL", "median_country_inflation", "country_rates")) == 1

    # Bounded LRU cache eviction
    monkeypatch.setattr(store_mod, "_READ_CACHE_MAX_ENTRIES", 2)
    store_mod._cache_put(("k1",), {"a": 1})
    store_mod._cache_put(("k2",), {"a": 2})
    store_mod._cache_put(("k3",), {"a": 3})
    assert len(store_mod._READ_CACHE) == 2
    assert ("k1",) not in store_mod._READ_CACHE
