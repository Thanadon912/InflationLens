from __future__ import annotations

import gzip
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.providers.base import FetchBundle, SourcePoint, utc_now

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
CREATE TABLE IF NOT EXISTS observation_lineage (
  derived_observation_id TEXT NOT NULL REFERENCES normalized_observations(id),
  source_observation_id TEXT NOT NULL REFERENCES normalized_observations(id),
  PRIMARY KEY (derived_observation_id, source_observation_id)
);
CREATE TABLE IF NOT EXISTS indicator_results (
  id TEXT PRIMARY KEY, sync_run_id TEXT NOT NULL REFERENCES sync_runs(id),
  geography TEXT NOT NULL, indicator_id TEXT NOT NULL, period TEXT NOT NULL,
  calculated_at TEXT NOT NULL, methodology_version TEXT NOT NULL,
  config_version TEXT, source_vintages TEXT NOT NULL, result_json TEXT NOT NULL,
  UNIQUE(sync_run_id, geography, indicator_id, period)
);
CREATE INDEX IF NOT EXISTS ix_result_lookup ON indicator_results(geography, indicator_id, period, calculated_at);
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
        with self.connect() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        try:
            yield db
            db.commit()
        finally:
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
        with self.connect() as db:
            db.execute("INSERT INTO sync_issues VALUES(?,?,?,?,?,?,?,?,?,?)", (issue_id, run_id, severity, provider, geography, indicator_id, code, message, json.dumps(details or {}, sort_keys=True), utc_now()))
        return issue_id

    def latest_observations(self, geography: str, indicator_id: str, role: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = [geography, indicator_id]
        where = "geography=? AND indicator_id=?"
        if role:
            where += " AND role=?"
            params.append(role)
        with self.connect() as db:
            rows = db.execute(f"SELECT * FROM normalized_observations WHERE {where} ORDER BY retrieved_at DESC, rowid DESC", params).fetchall()
        latest: dict[tuple, dict] = {}
        for row in rows:
            item = dict(row)
            key = (item["role"], item["component_id"], item["source_series_id"], item["observation_period"])
            latest.setdefault(key, item)
        return list(latest.values())

    def save_result(self, run_id: str, geography: str, indicator_id: str, period: str, result: dict, source_vintages: list[str]) -> str:
        snapshot_id = str(uuid.uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO indicator_results VALUES(?,?,?,?,?,?,?,?,?,?)", (snapshot_id, run_id, geography, indicator_id, period, result["calculated_at"], result["methodology_version"], result.get("config_version"), json.dumps(sorted(set(source_vintages))), json.dumps(result, sort_keys=True)))
        return snapshot_id

    def get_result(self, geography: str, indicator_id: str, period: str = "latest") -> dict[str, Any] | None:
        where = "geography=? AND indicator_id=?"
        params: list[Any] = [geography, indicator_id]
        if period != "latest":
            where += " AND period=?"
            params.append(period)
        with self.connect() as db:
            row = db.execute(f"SELECT * FROM indicator_results WHERE {where} ORDER BY period DESC,calculated_at DESC LIMIT 1", params).fetchone()
        if row is None:
            return None
        item = dict(row)
        item["result"] = json.loads(item.pop("result_json"))
        item["source_vintages"] = json.loads(item["source_vintages"])
        return item

    def status(self) -> dict[str, Any]:
        with self.connect() as db:
            run = db.execute("SELECT * FROM sync_runs ORDER BY started_at DESC LIMIT 1").fetchone()
            counts = {name: db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in ("raw_responses", "normalized_observations", "indicator_results", "sync_issues")}
        return {"database": self.path.name, "latest_run": dict(run) if run else None, "counts": counts}

    def issues(self, run_id: str | None = None) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM sync_issues WHERE (? IS NULL OR sync_run_id=?) ORDER BY created_at DESC", (run_id, run_id)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
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
