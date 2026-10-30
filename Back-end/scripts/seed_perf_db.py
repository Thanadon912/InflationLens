#!/usr/bin/env python3
"""Seed a *production-sized* deterministic SQLite cache for load testing.

scripts/seed_e2e_db.py seeds the smallest store that makes the frontend
render -- three countries, two periods, four regions. That is exactly
right for an E2E assertion and exactly wrong for a load test: every read
endpoint would serve a payload a fraction of its real size, and the
resulting latency numbers would flatter the API rather than measure it.
`/world/cross-section` in particular iterates every country the World
Bank publishes (~190), not three.

So this script seeds the same store, through the same public API
(SnapshotStore.save_point + IngestionService.calculate_available -- no
raw SQL, no schema knowledge), at the volume `flask data sync` actually
produces:

  * 7 US headline measures x 24 monthly results  (the registry's own
    monthly_backfill_periods), seeded with 36 months of index
    observations so all 24 have their year-ago comparison
  * 4 census regions x 24 monthly results -> /regions/us fills all 50 states
  * 6 essential-cost categories x 24 months
  * every country in app/config/iso_numeric.yaml in the global
    cross-section
  * EA alongside USA, plus the FOMC/labour context strip and the
    quarterly economy-wide series

Deterministic and offline: values come from a fixed drift formula, never
a provider and never a random seed, so two runs produce byte-identical
inputs and load-test numbers stay comparable across days.

Usage:
    python scripts/seed_perf_db.py [output_path]

If omitted, output_path defaults to $INFLATION_DB_PATH, falling back to
instance/perf-seed.sqlite3. Safe to re-run: it truncates any existing
file at that path first.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config.loader import load_iso_numeric
# _months_before is private, and imported anyway: it is the same period
# arithmetic the ingestion service uses to decide which months a result
# can be calculated for. Reimplementing it here would let the seed and the
# service disagree about what "twelve months back" means, which is exactly
# the bug that would make a seeded period silently uncalculable.
from app.data.service import IngestionService, _months_before
from app.data.store import SnapshotStore
from app.providers.base import FetchBundle, SourcePoint

# The latest period every series is seeded up to. Fixed rather than
# "today" so a run in September and a run in March seed identical data --
# a load test that silently changes shape over time cannot be compared
# against its own baseline.
ANCHOR_MONTH = "2026-07"
ANCHOR_QUARTER = "2026-Q2"

# 24 results per measure is monthly_backfill_periods; the extra 12 months
# supply each of those a year-ago index to compute YoY against.
RESULT_MONTHS = 24
SEED_MONTHS = RESULT_MONTHS + 12


def _mapping_for(registry, **want):
    for m in registry["sources"]:
        if all(m.get(k) == v for k, v in want.items()):
            return m
    raise AssertionError(f"no mapping matching {want!r}")


def _months(count: int, anchor: str = ANCHOR_MONTH) -> list[str]:
    """`count` consecutive months ending at `anchor`, oldest first."""
    return [_months_before(anchor, offset) for offset in reversed(range(count))]


def _quarters(count: int, anchor: str = ANCHOR_QUARTER) -> list[str]:
    year, quarter = int(anchor[:4]), int(anchor[-1])
    out = []
    for offset in reversed(range(count)):
        total = year * 4 + (quarter - 1) - offset
        out.append(f"{total // 4:04d}-Q{total % 4 + 1}")
    return out


def _index_series(periods: list[str], base: float, annual_percent: float, *, per_year: int = 12) -> dict[str, float]:
    """An index rising at `annual_percent` a year, compounded once per
    period, with a small deterministic wobble on top.

    Every measure gets its own base and rate so the /measures ledger shows
    a realistic spread rather than identical rows. The wobble matters too:
    a perfectly smooth curve makes the 1-month, 6-month-annualised and
    12-month windows return the *same* number, so the frontend's window
    rail would look broken and a load test could not tell the three code
    paths apart. A fixed sine keeps the series reproducible -- no RNG, no
    seed to remember -- while giving each window something different to
    compute.
    """

    step_rate = (1 + annual_percent / 100) ** (1 / per_year)
    return {
        period: round(base * step_rate**step * (1 + 0.004 * math.sin(step * 1.1)), 4)
        for step, period in enumerate(periods)
    }


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

    raw = {p: bundle_for(p) for p in ("bls", "bea", "fred", "eurostat", "ecb", "world_bank")}
    months = _months(SEED_MONTHS)
    quarters = _quarters(12)

    _seed_us_headline(store, service, registry, run, raw, months)
    _seed_essential(store, service, run, raw, months)
    _seed_money_and_gdp(store, service, run, raw, months, quarters)
    _seed_ea(store, service, registry, run, raw, months)
    _seed_context(store, run, raw, months)
    _seed_world(store, run, raw)

    store.finish_run(run, successes=1, failures=0)

    counts = store.status()["counts"]
    print(f"Seeded {db_path}")
    print(f"  observations: {counts['normalized_observations']}   results: {counts['indicator_results']}   issues: {counts['sync_issues']}")


def _seed_us_headline(store, service, registry, run, raw, months) -> None:
    """Seven published measures plus four census regions -- the ledger
    behind /measures/USA and /regions/us."""

    # (measure_id, starting index level, annual drift %). Six index
    # measures; `trim` is handled below because the Dallas Fed publishes
    # it as a rate with no underlying index (source_registry.yaml's
    # is_rate mapping).
    measures = (
        ("cpi", 320.0, 3.4),
        ("core", 300.0, 3.0),
        ("ccpi", 190.0, 3.1),
        ("ppi", 145.0, 2.6),
        ("pce", 128.0, 2.9),
        ("cpce", 126.0, 2.8),
    )
    for measure_id, base, rate in measures:
        mapping = _mapping_for(registry, geography="USA", indicator_id="headline_consumer_inflation", role="all_items_cpi_index", measure_id=measure_id, region_id=None)
        for period, value in _index_series(months, base, rate).items():
            store.save_point(run, raw[mapping["provider"]], SourcePoint(mapping, period, value))

    # Trimmed-mean PCE: a published percent-change series, stored as
    # issued (service._save_published_rate serves it untouched).
    trim = _mapping_for(registry, geography="USA", indicator_id="headline_consumer_inflation", role="all_items_cpi_index", measure_id="trim")
    for step, period in enumerate(months[-RESULT_MONTHS:]):
        store.save_point(run, raw["fred"], SourcePoint(trim, period, round(2.7 + 0.02 * step, 4)))

    # FRED's CPIAUCNS shadow of the BLS primary, kept inside the
    # registry's cross_source_index_tolerance so the ledger has its
    # second opinion without manufacturing a spurious data issue.
    shadow = _mapping_for(registry, geography="USA", indicator_id="headline_consumer_inflation", role="shadow_index")
    for period, value in _index_series(months, 320.0, 3.4).items():
        store.save_point(run, raw["fred"], SourcePoint(shadow, period, value))

    for region, rate in (("Northeast", 3.2), ("Midwest", 3.1), ("South", 3.6), ("West", 3.5)):
        mapping = _mapping_for(registry, geography="USA", indicator_id="headline_consumer_inflation", role="all_items_cpi_index", measure_id="cpi", region_id=region)
        for period, value in _index_series(months, 100.0, rate).items():
            store.save_point(run, raw["bls"], SourcePoint(mapping, period, value))

    service.calculate_available(run, "USA", "headline_consumer_inflation")


def _seed_essential(store, service, run, raw, months) -> None:
    """The category ladder behind /categories/USA. category_rates are
    already year-over-year, so every seeded month yields a result and
    only the newest RESULT_MONTHS are kept by the backfill window."""

    categories = (("food", 3.0), ("housing", 3.2), ("energy", 14.7), ("transport", 2.5), ("healthcare", 3.0), ("communications", 1.0))
    for cat, rate in categories:
        mapping = {"provider": "bls", "series_id": f"yoy:{cat}", "indicator_id": "essential_cost_inflation", "role": "category_rates", "geography": "USA", "component_id": cat, "frequency": "monthly", "unit": "percent_yoy"}
        for step, period in enumerate(months[-RESULT_MONTHS:]):
            store.save_point(run, raw["bls"], SourcePoint(mapping, period, round(rate + 0.05 * step, 4)))
    service.calculate_available(run, "USA", "essential_cost_inflation")


def _seed_money_and_gdp(store, service, run, raw, months, quarters) -> None:
    money = {"provider": "fred", "series_id": "M2SL", "indicator_id": "broad_money_expansion", "role": "money_level", "geography": "USA", "frequency": "monthly", "unit": "local_currency", "currency": "USD"}
    for period, value in _index_series(months, 21000.0, 4.2).items():
        store.save_point(run, raw["fred"], SourcePoint(money, period, value))
    service.calculate_available(run, "USA", "broad_money_expansion")

    nominal = {"provider": "bea", "series_id": "NIPA:T10105:1", "indicator_id": "economy_wide_inflation", "role": "nominal_gdp", "geography": "USA", "frequency": "quarterly", "unit": "local_currency", "currency": "USD"}
    real = {**nominal, "series_id": "NIPA:T10106:1", "role": "real_gdp"}
    for period, value in _index_series(quarters, 28000.0, 5.1, per_year=4).items():
        store.save_point(run, raw["bea"], SourcePoint(nominal, period, value))
    for period, value in _index_series(quarters, 23000.0, 2.3, per_year=4).items():
        store.save_point(run, raw["bea"], SourcePoint(real, period, value))
    service.calculate_available(run, "USA", "economy_wide_inflation")


def _seed_ea(store, service, registry, run, raw, months) -> None:
    """EA is the second geography the frontend's rail can switch to, so
    /measures/EA has to serve a real payload too -- one HICP measure and
    the same category ladder."""

    hicp = _mapping_for(registry, geography="EA", indicator_id="headline_consumer_inflation", role="all_items_cpi_index", measure_id="cpi")
    for period, value in _index_series(months, 125.0, 2.4).items():
        store.save_point(run, raw["eurostat"], SourcePoint(hicp, period, value))
    service.calculate_available(run, "EA", "headline_consumer_inflation")

    for cat, rate in (("food", 2.8), ("housing", 2.1), ("energy", 9.4), ("transport", 1.9), ("healthcare", 2.2), ("communications", 0.4)):
        mapping = {"provider": "eurostat", "series_id": f"yoy:ea:{cat}", "indicator_id": "essential_cost_inflation", "role": "category_rates", "geography": "EA", "component_id": cat, "frequency": "monthly", "unit": "percent_yoy"}
        for step, period in enumerate(months[-RESULT_MONTHS:]):
            store.save_point(run, raw["eurostat"], SourcePoint(mapping, period, round(rate + 0.04 * step, 4)))
    service.calculate_available(run, "EA", "essential_cost_inflation")


def _seed_context(store, run, raw, months) -> None:
    """The FOMC/labour strip /measures/USA appends. Fed target is a daily
    FRED series in production; monthly here is enough for the endpoint's
    max-period reduction to have more than one row to choose between."""

    context = {"provider": "fred", "series_id": "DFEDTARU", "indicator_id": "context_metadata", "role": "fed_target_upper", "geography": "USA", "frequency": "monthly", "unit": "percent"}
    recent = months[-RESULT_MONTHS:]
    for step, period in enumerate(recent):
        store.save_point(run, raw["fred"], SourcePoint(context, period, round(5.5 - 0.07 * step, 4)))
        store.save_point(run, raw["fred"], SourcePoint({**context, "series_id": "FEDFUNDS", "role": "fed_funds_rate"}, period, round(5.33 - 0.07 * step, 4)))
        store.save_point(run, raw["fred"], SourcePoint({**context, "series_id": "UNRATE", "role": "unemployment_rate"}, period, round(3.7 + 0.02 * step, 4)))

    # Wage growth is an average-hourly-earnings *level*; the read
    # endpoint derives its YoY, so it needs the full 36 months.
    wage = {**context, "series_id": "CES0500000003", "role": "wage_growth", "unit": "local_currency", "currency": "USD"}
    for period, value in _index_series(months, 29.5, 4.0).items():
        store.save_point(run, raw["fred"], SourcePoint(wage, period, value))

    population = {"provider": "world_bank", "series_id": "SP.POP.TOTL", "indicator_id": "geography_metadata", "role": "population", "geography": "USA", "frequency": "annual", "unit": "persons"}
    store.save_point(run, raw["world_bank"], SourcePoint(population, "2024", 336_000_000.0))
    store.save_point(run, raw["world_bank"], SourcePoint({**population, "geography": "EA"}, "2024", 350_000_000.0))


def _seed_world(store, run, raw) -> None:
    """Every country the choropleth can shade. iso_numeric.yaml is the
    join table /world/cross-section already uses, so seeding from it
    guarantees the endpoint's loop runs over its full real width instead
    of discarding most rows as unmappable."""

    named_overrides: dict[str, tuple[str, float]] = {
        "ARG": ("Argentina", 117.8),
        "TUR": ("Turkiye", 44.4),
        "NGA": ("Nigeria", 32.7),
        "EGY": ("Egypt", 26.5),
        "USA": ("United States", 3.4),
        "DEU": ("Germany", 2.3),
        "FRA": ("France", 2.2),
        "GBR": ("United Kingdom", 2.6),
        "JPN": ("Japan", 2.8),
        "CHN": ("China", 0.6),
        "IND": ("India", 4.8),
        "BRA": ("Brazil", 4.4),
        "CAN": ("Canada", 2.5),
        "AUS": ("Australia", 3.5),
        "CHE": ("Switzerland", 1.1),
    }

    mapping = {"provider": "world_bank", "series_id": "FP.CPI.TOTL.ZG", "indicator_id": "median_country_inflation", "role": "country_rates", "geography": "GLOBAL", "frequency": "annual", "unit": "percent_yoy"}
    for step, iso3 in enumerate(sorted(load_iso_numeric())):
        if iso3 in named_overrides:
            display_name, value = named_overrides[iso3]
        else:
            display_name = iso3
            # Realistic cross-section distribution centered around ~3.1%
            value = round(0.4 + (step % 28) * 0.22, 4)
        store.save_point(run, raw["world_bank"], SourcePoint({**mapping, "component_id": iso3}, "2024", value, provider_status=display_name))


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(os.environ.get("INFLATION_DB_PATH", "instance/perf-seed.sqlite3"))
    seed(target)
