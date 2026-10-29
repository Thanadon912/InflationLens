from __future__ import annotations

import copy
import gzip
import json
import os
import sqlite3
import uuid
from collections import OrderedDict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.providers.base import FetchBundle, SourcePoint, sanitize_text, utc_now

# Sentinel distinguishing "do not filter on this column" from the legitimate
# filter value ``None`` (== "only rows where the column IS NULL"), needed by
# SnapshotStore.list_latest_results below.
_UNSET = object()

# Process-local cache of already-initialized SQLite files (path, st_dev, st_ino)
# so per-request SnapshotStore() instantiations skip redundant DDL/migration
# checks once a database file has been verified.
_INITIALIZED_DB_FILES: set[tuple[str, int, int]] = set()
_WRITE_GEN: dict[str, int] = {}
_READ_CACHE: OrderedDict[tuple[Any, ...], Any] = OrderedDict()
_READ_CACHE_MAX_ENTRIES = 256


def _db_file_identity(path: Path) -> tuple[str, int, int] | None:
    if not path.exists():
        return None
    st = path.stat()
    return None if st.st_size == 0 else (str(path), st.st_dev, st.st_ino)


def _db_state_token(path: Path) -> tuple[Any, ...]:
    key = str(path)
    gen = _WRITE_GEN.get(key, 0)
    st = path.stat()
    wal_path = Path(f"{path}-wal")
    wal_sig = (wal_path.stat().st_mtime_ns, wal_path.stat().st_size) if wal_path.exists() else (0, 0)
    return (key, gen, (st.st_ino, st.st_mtime_ns, st.st_size), wal_sig)


def _cache_get(cache_key: tuple[Any, ...]) -> tuple[bool, Any]:
    if cache_key in _READ_CACHE:
        _READ_CACHE.move_to_end(cache_key)
        return True, copy.deepcopy(_READ_CACHE[cache_key])
    return False, None


def _cache_put(cache_key: tuple[Any, ...], value: Any) -> None:
    _READ_CACHE[cache_key] = copy.deepcopy(value)
    _READ_CACHE.move_to_end(cache_key)
    while len(_READ_CACHE) > _READ_CACHE_MAX_ENTRIES:
        _READ_CACHE.popitem(last=False)


class CorruptCacheError(RuntimeError):
    """A cached JSON blob (result_json/source_vintages/details_json) failed
    to decode. This is a server-side data-integrity fault, not a caller
    input problem -- it stays a 500, but with a diagnosable message naming
    the row and column instead of a bare json.JSONDecodeError traceback."""


def _safe_json_loads(raw: str, *, column: str, row_id: str | None) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CorruptCacheError(f"Corrupt cached JSON in column {column!r} (row id={row_id!r}): {exc}") from exc

SCHEMA = """
CREATE TABLE IF NOT EXISTS sync_runs (
  id TEXT PRIMARY KEY, started_at TEXT NOT NULL, completed_at TEXT,
  status TEXT NOT NULL, requested_geography TEXT NOT NULL,
  requested_indicator TEXT NOT NULL, successes INTEGER NOT NULL DEFAULT 0,
  failures INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS raw_responses (
  id TEXT PRIMARY KEY, sync_run_id TEXT NOT NULL REFERENCES sync_runs(id),
  provider TEXT NOT NULL, request_url TEXT NOT NULL, retrieved_at TEXT NOT NULL,
  content_type TEXT NOT NULL, sha256 TEXT NOT NULL, body_gzip BLOB NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_raw_sha ON raw_responses(sha256);
CREATE TABLE IF NOT EXISTS normalized_observations (
  id TEXT PRIMARY KEY, sync_run_id TEXT NOT NULL REFERENCES sync_runs(id),
  raw_response_id TEXT REFERENCES raw_responses(id), provider TEXT NOT NULL,
  source_series_id TEXT NOT NULL, indicator_id TEXT NOT NULL, role TEXT NOT NULL,
  geography TEXT NOT NULL, component_id TEXT, frequency TEXT NOT NULL,
  unit TEXT NOT NULL, currency TEXT, observation_period TEXT NOT NULL,
  value REAL NOT NULL, retrieved_at TEXT NOT NULL, publication_date TEXT,
  seasonally_adjusted INTEGER, source_url TEXT, is_estimated INTEGER NOT NULL,
  is_revised INTEGER NOT NULL, data_vintage TEXT, provider_status TEXT,
  validation_status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_obs_lookup ON normalized_observations(geography, indicator_id, role, observation_period, retrieved_at);
CREATE INDEX IF NOT EXISTS ix_obs_component ON normalized_observations(geography, indicator_id, role, component_id, observation_period, retrieved_at);
CREATE TABLE IF NOT EXISTS observation_lineage (
  derived_observation_id TEXT NOT NULL REFERENCES normalized_observations(id),
  source_observation_id TEXT NOT NULL REFERENCES normalized_observations(id),
  PRIMARY KEY (derived_observation_id, source_observation_id)
);
CREATE TABLE IF NOT EXISTS indicator_results (
  id TEXT PRIMARY KEY, sync_run_id TEXT NOT NULL REFERENCES sync_runs(id),
  geography TEXT NOT NULL, indicator_id TEXT NOT NULL, measure_id TEXT, region_id TEXT,
  period TEXT NOT NULL, calculated_at TEXT NOT NULL, methodology_version TEXT NOT NULL,
  config_version TEXT, source_vintages TEXT NOT NULL, result_json TEXT NOT NULL
);
-- indicator_results' indexes are created in SnapshotStore._migrate_indicator_results
-- instead of here: a database created before measure_id/region_id existed still has
-- the old columnless table at this point (CREATE TABLE IF NOT EXISTS is a no-op
-- against it), and an index naming those columns would fail to create until after
-- that method's rebuild runs.
CREATE TABLE IF NOT EXISTS sync_issues (
  id TEXT PRIMARY KEY, sync_run_id TEXT NOT NULL REFERENCES sync_runs(id),
  severity TEXT NOT NULL, provider TEXT, geography TEXT, indicator_id TEXT,
  code TEXT NOT NULL, message TEXT NOT NULL, details_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


class SnapshotStore:
    def __init__(self, path: str | Path | None = None) -> None:
        configured = path or os.environ.get("INFLATION_DB_PATH", "instance/inflation_lens.sqlite3")
        self.path = Path(configured)
        if not self.path.is_absolute():
            self.path = Path.cwd() / self.path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        identity = _db_file_identity(self.path)
        if identity is None or identity not in _INITIALIZED_DB_FILES:
            with self.connect() as db:
                db.executescript(SCHEMA)
                self._migrate_indicator_results(db)
            _INITIALIZED_DB_FILES.add(_db_file_identity(self.path))  # type: ignore[arg-type]

    def _migrate_indicator_results(self, db: sqlite3.Connection) -> None:
        """Add the measure_id/region_id dimension to a pre-existing database.

        ``CREATE TABLE IF NOT EXISTS`` in ``SCHEMA`` is a no-op against a
        database created before ``headline_consumer_inflation`` gained
        per-measure and per-region cached results (source_registry.yaml's
        seven US measures and four regional CPI series), so its
        ``indicator_results`` table is still bound by the old
        ``UNIQUE(sync_run_id, geography, indicator_id, period)`` constraint.
        SQLite cannot drop or alter a table constraint in place; the table
        is rebuilt under its new shape and every existing row is preserved
        with ``measure_id``/``region_id`` set to ``NULL`` (undated results
        keep meaning "the one series this geography/indicator had before").
        """

        columns = {row["name"] for row in db.execute("PRAGMA table_info(indicator_results)")}
        if "measure_id" not in columns:
            db.executescript(
                """
                ALTER TABLE indicator_results RENAME TO indicator_results_pre_measure;
                CREATE TABLE indicator_results (
                  id TEXT PRIMARY KEY, sync_run_id TEXT NOT NULL REFERENCES sync_runs(id),
                  geography TEXT NOT NULL, indicator_id TEXT NOT NULL, measure_id TEXT, region_id TEXT,
                  period TEXT NOT NULL, calculated_at TEXT NOT NULL, methodology_version TEXT NOT NULL,
                  config_version TEXT, source_vintages TEXT NOT NULL, result_json TEXT NOT NULL
                );
                INSERT INTO indicator_results
                  (id, sync_run_id, geography, indicator_id, measure_id, region_id, period, calculated_at, methodology_version, config_version, source_vintages, result_json)
                  SELECT id, sync_run_id, geography, indicator_id, NULL, NULL, period, calculated_at, methodology_version, config_version, source_vintages, result_json
                  FROM indicator_results_pre_measure;
                DROP TABLE indicator_results_pre_measure;
                """
            )
        # Runs every open, fresh database or migrated: cheap and idempotent
        # (IF NOT EXISTS), and the one safe place to create these -- a
        # fresh database's indicator_results already has the columns via
        # SCHEMA above, and a legacy one only gained them just now.
        db.executescript(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_result_variant ON indicator_results(sync_run_id, geography, indicator_id, measure_id, region_id, period);
            CREATE INDEX IF NOT EXISTS ix_result_lookup ON indicator_results(geography, indicator_id, period, calculated_at);
            """
        )

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        # Every call opens its own connection (see module docstring context);
        # under a concurrent `data sync`, two writers can otherwise collide
        # as a raw "database is locked" OperationalError. A busy_timeout
        # makes SQLite retry internally for up to 5s before that surfaces,
        # rather than failing immediately on first contention.
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
            db.commit()
        finally:
            if db.total_changes > 0:
                _WRITE_GEN[str(self.path)] = _WRITE_GEN.get(str(self.path), 0) + 1
            db.close()

    def create_run(self, geography: str, indicator: str) -> str:
        run_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO sync_runs(id,started_at,status,requested_geography,requested_indicator) VALUES(?,?,?,?,?)", (run_id, utc_now(), "running", geography, indicator))
        return run_id

    def finish_run(self, run_id: str, *, successes: int, failures: int) -> None:
        status = "success" if failures == 0 else "partial" if successes else "failed"
        with self.connect() as db:
            db.execute("UPDATE sync_runs SET completed_at=?,status=?,successes=?,failures=? WHERE id=?", (utc_now(), status, successes, failures, run_id))

    def save_bundle(self, run_id: str, bundle: FetchBundle) -> str:
        raw_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO raw_responses VALUES(?,?,?,?,?,?,?,?)", (raw_id, run_id, bundle.provider, bundle.request_url, bundle.retrieved_at, bundle.content_type, bundle.sha256, gzip.compress(bundle.body)))
        return raw_id

    def save_point(self, run_id: str, raw_id: str | None, point: SourcePoint, *, role: str | None = None, value: float | None = None, unit: str | None = None, provider: str | None = None, source_series_id: str | None = None, lineage: tuple[str, ...] = ()) -> str:
        m = point.mapping
        obs_id = str(uuid.uuid4())
        actual_role = role or m["role"]
        actual_value = point.value if value is None else value
        revised = point.is_revised or self._has_changed_value(m["geography"], m["indicator_id"], actual_role, m.get("component_id"), point.period, actual_value)
        with self.connect() as db:
            db.execute(
                """INSERT INTO normalized_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (obs_id, run_id, raw_id, provider or m["provider"], source_series_id or m["series_id"], m["indicator_id"], actual_role, m["geography"], m.get("component_id"), m["frequency"], unit or m["unit"], m.get("currency"), point.period, actual_value, point.mapping.get("retrieved_at", utc_now()) if raw_id is None else self._raw_retrieved_at(raw_id), point.publication_date, _bool(m.get("seasonally_adjusted")), m.get("source_url"), int(point.is_estimated), int(revised), point.data_vintage, point.provider_status, "validated"),
            )
            db.executemany("INSERT INTO observation_lineage VALUES(?,?)", [(obs_id, source_id) for source_id in lineage])
        return obs_id

    def _raw_retrieved_at(self, raw_id: str) -> str:
        with self.connect() as db:
            return db.execute("SELECT retrieved_at FROM raw_responses WHERE id=?", (raw_id,)).fetchone()[0]

    def _has_changed_value(self, geography, indicator, role, component, period, value) -> bool:
        with self.connect() as db:
            row = db.execute("""SELECT value FROM normalized_observations WHERE geography=? AND indicator_id=? AND role=? AND component_id IS ? AND observation_period=? ORDER BY retrieved_at DESC, rowid DESC LIMIT 1""", (geography, indicator, role, component, period)).fetchone()
        return row is not None and float(row["value"]) != float(value)

    def add_issue(self, run_id: str, code: str, message: str, *, severity: str = "error", provider: str | None = None, geography: str | None = None, indicator_id: str | None = None, details: dict | None = None) -> str:
        issue_id = str(uuid.uuid4())
        safe_message = sanitize_text(message)
        with self.connect() as db:
            db.execute("INSERT INTO sync_issues VALUES(?,?,?,?,?,?,?,?,?,?)", (issue_id, run_id, severity, provider, geography, indicator_id, code, safe_message, json.dumps(details or {}, sort_keys=True), utc_now()))
        return issue_id

    def latest_observations(self, geography: str, indicator_id: str, role: str | None = None) -> list[dict[str, Any]]:
        cache_key = ("latest_observations", _db_state_token(self.path), geography, indicator_id, role)
        hit, cached = _cache_get(cache_key)
        if hit:
            return cached
        query = (
            "SELECT * FROM ("
            "  SELECT *, rowid AS _orig_rowid, ROW_NUMBER() OVER ("
            "    PARTITION BY role, component_id, source_series_id, observation_period "
            "    ORDER BY retrieved_at DESC, rowid DESC"
            "  ) AS _rn "
            "  FROM normalized_observations "
            "  WHERE geography=? AND indicator_id=? AND (? IS NULL OR role=?)"
            ") WHERE _rn = 1 ORDER BY retrieved_at DESC, _orig_rowid DESC"
        )
        with self.connect() as db:
            rows = db.execute(query, (geography, indicator_id, role, role)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item.pop("_rn", None)
            item.pop("_orig_rowid", None)
            result.append(item)
        _cache_put(cache_key, result)
        return copy.deepcopy(result)

    def latest_retrieval_by_provider(self) -> dict[str, str]:
        """The most recent ``retrieved_at`` timestamp raw-response fetched
        from each provider -- the real "latest release" figure the source
        ledger (GET /api/v1/meta/data-sources) prints per publisher, as
        opposed to an invented release-calendar date."""

        with self.connect() as db:
            rows = db.execute("SELECT provider, MAX(retrieved_at) AS latest FROM raw_responses GROUP BY provider").fetchall()
        return {row["provider"]: row["latest"] for row in rows}

    def latest_by_component(self, geography: str, indicator_id: str, role: str) -> list[dict[str, Any]]:
        """Collapse ``latest_observations`` to one row per ``component_id``:
        the most recent ``observation_period`` each has published.

        Built for cross-sectional reads where every component publishes on
        its own schedule -- e.g. the world choropleth's ~190 countries
        (``median_country_inflation``/``country_rates``, one row per ISO3),
        where ``latest_observations`` alone would return every historical
        year for every country rather than just each country's newest one.
        """

        cache_key = ("latest_by_component", _db_state_token(self.path), geography, indicator_id, role)
        hit, cached = _cache_get(cache_key)
        if hit:
            return cached
        query = (
            "SELECT * FROM ("
            "  SELECT *, rowid AS _orig_rowid, ROW_NUMBER() OVER ("
            "    PARTITION BY component_id "
            "    ORDER BY observation_period DESC, retrieved_at DESC, rowid DESC"
            "  ) AS _rn "
            "  FROM normalized_observations "
            "  WHERE geography=? AND indicator_id=? AND role=?"
            ") WHERE _rn = 1 ORDER BY retrieved_at DESC, _orig_rowid DESC"
        )
        with self.connect() as db:
            rows = db.execute(query, (geography, indicator_id, role)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item.pop("_rn", None)
            item.pop("_orig_rowid", None)
            result.append(item)
        _cache_put(cache_key, result)
        return copy.deepcopy(result)

    def save_result(self, run_id: str, geography: str, indicator_id: str, period: str, result: dict, source_vintages: list[str], *, measure_id: str | None = None, region_id: str | None = None) -> str:
        snapshot_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute(
                "INSERT INTO indicator_results (id,sync_run_id,geography,indicator_id,measure_id,region_id,period,calculated_at,methodology_version,config_version,source_vintages,result_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (snapshot_id, run_id, geography, indicator_id, measure_id, region_id, period, result["calculated_at"], result["methodology_version"], result.get("config_version"), json.dumps(sorted(set(source_vintages))), json.dumps(result, sort_keys=True)),
            )
        return snapshot_id

    def get_result(
        self,
        geography: str,
        indicator_id: str,
        period: str = "latest",
        *,
        measure_id: str | None = None,
        region_id: str | None = None,
        methodology_version: str | None = None,
        config_version: str | None = None,
    ) -> dict[str, Any] | None:
        # `headline_consumer_inflation` caches seven US measures side by
        # side (source_registry.yaml); a caller that does not name one
        # gets the primary CPI-U series, matching this indicator's single
        # cached series before measures existed. Every other indicator has
        # always had exactly one series, so its rows carry measure_id=NULL
        # and an unset filter already resolves them correctly.
        if measure_id is None and indicator_id == "headline_consumer_inflation":
            measure_id = "cpi"
        cache_key = (
            "get_result",
            _db_state_token(self.path),
            geography,
            indicator_id,
            period,
            measure_id,
            region_id,
            methodology_version,
            config_version,
        )
        hit, cached = _cache_get(cache_key)
        if hit:
            return cached
        query = (
            "SELECT * FROM indicator_results "
            "WHERE geography=? AND indicator_id=? AND measure_id IS ? AND region_id IS ? "
            "  AND (? = 'latest' OR period=?) "
            "  AND (? IS NULL OR methodology_version=?) "
            "  AND (? IS NULL OR config_version=?) "
            "ORDER BY period DESC, calculated_at DESC LIMIT 1"
        )
        params = (
            geography,
            indicator_id,
            measure_id,
            region_id,
            period,
            period,
            methodology_version,
            methodology_version,
            config_version,
            config_version,
        )
        with self.connect() as db:
            row = db.execute(query, params).fetchone()
        if row is None:
            _cache_put(cache_key, None)
            return None
        item = dict(row)
        item["result"] = _safe_json_loads(item.pop("result_json"), column="result_json", row_id=item.get("id"))
        item["source_vintages"] = _safe_json_loads(item["source_vintages"], column="source_vintages", row_id=item.get("id"))
        _cache_put(cache_key, item)
        return copy.deepcopy(item)

    def list_latest_results(
        self,
        geography: str,
        indicator_id: str,
        *,
        measure_id: Any = _UNSET,
        region_id: Any = _UNSET,
        methodology_version: str | None = None,
        config_version: str | None = None,
    ) -> list[dict[str, Any]]:
        """Every distinct measure_id/region_id variant cached for this
        geography/indicator, each at its own latest available period.

        Used by the /measures and /regions read endpoints (app/api/data.py)
        to list the seven US price measures, or the four census regions,
        side by side -- ``get_result`` above answers "the one figure for
        this period"; this answers "every figure currently on screen".
        Pass ``measure_id``/``region_id`` to narrow to one dimension
        (``None`` filters for that column being unset, not "don't care").
        """

        cache_key = (
            "list_latest_results",
            _db_state_token(self.path),
            geography,
            indicator_id,
            "__UNSET__" if measure_id is _UNSET else measure_id,
            "__UNSET__" if region_id is _UNSET else region_id,
            methodology_version,
            config_version,
        )
        hit, cached = _cache_get(cache_key)
        if hit:
            return cached
        filter_measure = 0 if measure_id is _UNSET else 1
        measure_val = None if measure_id is _UNSET else measure_id
        filter_region = 0 if region_id is _UNSET else 1
        region_val = None if region_id is _UNSET else region_id
        query = (
            "SELECT * FROM ("
            "  SELECT *, rowid AS _orig_rowid, ROW_NUMBER() OVER ("
            "    PARTITION BY measure_id, region_id "
            "    ORDER BY period DESC, calculated_at DESC, rowid DESC"
            "  ) AS _rn "
            "  FROM indicator_results "
            "  WHERE geography=? AND indicator_id=? "
            "    AND (? = 0 OR measure_id IS ?) "
            "    AND (? = 0 OR region_id IS ?) "
            "    AND (? IS NULL OR methodology_version=?) "
            "    AND (? IS NULL OR config_version=?)"
            ") WHERE _rn = 1 ORDER BY period DESC, calculated_at DESC, _orig_rowid DESC"
        )
        params = (
            geography,
            indicator_id,
            filter_measure,
            measure_val,
            filter_region,
            region_val,
            methodology_version,
            methodology_version,
            config_version,
            config_version,
        )
        with self.connect() as db:
            rows = db.execute(query, params).fetchall()
        results = []
        for row in rows:
            item = dict(row)
            item.pop("_rn", None)
            item.pop("_orig_rowid", None)
            item["result"] = _safe_json_loads(item.pop("result_json"), column="result_json", row_id=item.get("id"))
            item["source_vintages"] = _safe_json_loads(item["source_vintages"], column="source_vintages", row_id=item.get("id"))
            results.append(item)
        _cache_put(cache_key, results)
        return copy.deepcopy(results)

    def status(self) -> dict[str, Any]:
        counts_query = (
            "SELECT "
            "  (SELECT COUNT(*) FROM raw_responses) AS raw_responses, "
            "  (SELECT COUNT(*) FROM normalized_observations) AS normalized_observations, "
            "  (SELECT COUNT(*) FROM indicator_results) AS indicator_results, "
            "  (SELECT COUNT(*) FROM sync_issues) AS sync_issues"
        )
        with self.connect() as db:
            run = db.execute("SELECT * FROM sync_runs ORDER BY started_at DESC LIMIT 1").fetchone()
            counts_row = db.execute(counts_query).fetchone()
        return {"database": self.path.name, "latest_run": dict(run) if run else None, "counts": dict(counts_row)}

    def issues(self, run_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM sync_issues WHERE (? IS NULL OR sync_run_id=?) ORDER BY created_at DESC", (run_id, run_id)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["details"] = _safe_json_loads(item.pop("details_json"), column="details_json", row_id=item.get("id"))
            result.append(item)
        return result

    def lineage(self, snapshot_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            result = db.execute("SELECT * FROM indicator_results WHERE id=?", (snapshot_id,)).fetchone()
            if result is None:
                return None
            observations = db.execute("SELECT * FROM normalized_observations WHERE sync_run_id=? AND geography=? AND indicator_id=?", (result["sync_run_id"], result["geography"], result["indicator_id"])).fetchall()
            raw = db.execute("SELECT id,provider,request_url,retrieved_at,content_type,sha256 FROM raw_responses WHERE sync_run_id=?", (result["sync_run_id"],)).fetchall()
        return {"snapshot": {k: result[k] for k in ("id", "sync_run_id", "geography", "indicator_id", "period", "calculated_at")}, "observations": [dict(row) for row in observations], "raw_responses": [dict(row) for row in raw]}


def _bool(value):
    return None if value is None else int(bool(value))
