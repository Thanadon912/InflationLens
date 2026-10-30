#!/usr/bin/env python3
"""Seed a small, deterministic SQLite cache for local dev / E2E runs.

The real `flask data sync` pulls from live BLS/FRED/BEA/Eurostat/ECB/World
Bank APIs -- not something an E2E run should depend on (network flakiness,
API keys, non-determinism, and it would make every CI run a live call
against those providers). This script seeds the exact same store shape
through the exact same public API (SnapshotStore.save_point +
IngestionService.calculate_available), the same way
tests/integration/test_read_endpoints.py's `seeded_store` fixture does for
the backend's own integration tests -- just written to a durable path
instead of a pytest tmp_path, so a Playwright webServer can start Flask
against it.

Usage:
    python scripts/seed_e2e_db.py [output_path]

If omitted, output_path defaults to $INFLATION_DB_PATH, falling back to
instance/e2e-seed.sqlite3. Safe to re-run: it truncates any existing file
at that path first.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.data.service import IngestionService
from app.data.store import SnapshotStore
from app.providers.base import FetchBundle, SourcePoint


def _mapping_for(registry, **want):
    for m in registry["sources"]:
        if all(m.get(k) == v for k, v in want.items()):
            return m
    raise AssertionError(f"no mapping matching {want!r}")


def seed(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    store = SnapshotStore(db_path)
    service = IngestionService(store)
    registry = service.registry

    run = store.create_run("USA", "headline_consumer_inflation")

    def bundle_for(provider):
        return store.save_bundle(run, FetchBundle(provider, f"https://example.test/{provider}", "2026-08-01T00:00:00Z", b"raw", "application/json", ()))

    bls_raw = bundle_for("bls")
    fred_raw = bundle_for("fred")
    world_bank_raw = bundle_for("world_bank")

    # Seven official measures: clean, computable YoY periods for all 7 gauges
    # (CPI-U: 3.6%, Core CPI: 3.2%, C-CPI-U: 3.3%, PPI: 2.8%, PCE: 3.1%, Core PCE: 3.0%, Trimmed: 3.2%)
    measure_rates = [
        ("cpi", 3.6, bls_raw),
        ("core", 3.2, bls_raw),
        ("ccpi", 3.3, bls_raw),
        ("ppi", 2.8, bls_raw),
        ("pce", 3.1, fred_raw),
        ("cpce", 3.0, fred_raw),
    ]
    for measure_id, rate, raw in measure_rates:
        m = _mapping_for(registry, geography="USA", indicator_id="headline_consumer_inflation", role="all_items_cpi_index", measure_id=measure_id, region_id=None)
        base = 100.0
        store.save_point(run, raw, SourcePoint(m, "2025-06", base))
        store.save_point(run, raw, SourcePoint(m, "2025-07", base))
        store.save_point(run, raw, SourcePoint(m, "2026-01", round(base * (1 + rate * 0.3 / 100), 4)))  # 6mo back from 2026-07, distinct momentum for 6m window
        store.save_point(run, raw, SourcePoint(m, "2026-06", round(base * (1 + rate * 0.9 / 100), 4)))
        store.save_point(run, raw, SourcePoint(m, "2026-07", round(base * (1 + rate / 100), 4)))

    m_trim = _mapping_for(registry, geography="USA", indicator_id="headline_consumer_inflation", role="all_items_cpi_index", measure_id="trim", region_id=None)
    store.save_point(run, fred_raw, SourcePoint(m_trim, "2026-07", 3.2))

    region_rates = {"Northeast": 3.2, "Midwest": 3.1, "South": 3.6, "West": 3.5}
    for region, rate in region_rates.items():
        m = _mapping_for(registry, geography="USA", indicator_id="headline_consumer_inflation", role="all_items_cpi_index", measure_id="cpi", region_id=region)
        store.save_point(run, bls_raw, SourcePoint(m, "2025-07", 100.0))
        store.save_point(run, bls_raw, SourcePoint(m, "2026-07", round(100.0 * (1 + rate / 100), 4)))

    service.calculate_available(run, "USA", "headline_consumer_inflation")

    for cat, rate in {"food": 3.0, "housing": 3.2, "energy": 14.7, "transport": 2.5, "healthcare": 3.0, "communications": 1.0}.items():
        m = {"provider": "bls", "series_id": f"yoy:{cat}", "indicator_id": "essential_cost_inflation", "role": "category_rates", "geography": "USA", "component_id": cat, "frequency": "monthly", "unit": "percent_yoy"}
        store.save_point(run, bls_raw, SourcePoint(m, "2026-07", rate))
    service.calculate_available(run, "USA", "essential_cost_inflation")

    fred_context = {"provider": "fred", "series_id": "DFEDTARU", "indicator_id": "context_metadata", "role": "fed_target_upper", "geography": "USA", "frequency": "monthly", "unit": "percent"}
    store.save_point(run, fred_raw, SourcePoint(fred_context, "2026-05", 4.5))
    store.save_point(run, fred_raw, SourcePoint(fred_context, "2026-07", 3.75))
    store.save_point(run, fred_raw, SourcePoint({**fred_context, "series_id": "FEDFUNDS", "role": "fed_funds_rate"}, "2026-07", 3.62))
    store.save_point(run, fred_raw, SourcePoint({**fred_context, "series_id": "UNRATE", "role": "unemployment_rate"}, "2026-07", 4.1))
    wage_mapping = {**fred_context, "series_id": "CES0500000003", "role": "wage_growth", "unit": "local_currency", "currency": "USD"}
    store.save_point(run, fred_raw, SourcePoint(wage_mapping, "2025-07", 30.0))
    store.save_point(run, fred_raw, SourcePoint(wage_mapping, "2026-07", 31.2))

    world_mapping = {"provider": "world_bank", "series_id": "FP.CPI.TOTL.ZG", "indicator_id": "median_country_inflation", "role": "country_rates", "geography": "GLOBAL", "frequency": "annual", "unit": "percent_yoy"}
    for iso3, name, value in (("USA", "United States", 3.0), ("FRA", "France", 2.4), ("VEN", "Venezuela, RB", 387.0)):
        store.save_point(run, world_bank_raw, SourcePoint({**world_mapping, "component_id": iso3}, "2024", value, provider_status=name))

    store.finish_run(run, successes=1, failures=0)
    print(f"Seeded {db_path}")


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("INFLATION_DB_PATH", "instance/e2e-seed.sqlite3"))
    seed(target)
