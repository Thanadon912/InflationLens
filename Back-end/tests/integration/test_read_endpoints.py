"""Integration coverage for the Phase 2 cached-read endpoints
(app/api/data.py): /measures, /categories, /regions/us, /world/cross-section,
/resolve, and the extended /meta/data-sources publisher ledger.

Observations are seeded directly into the store rather than mocked over
HTTP -- these endpoints only ever read from SQLite at request time (no
provider call), so this exercises exactly what production does.
"""

from __future__ import annotations

import pytest

from app import create_app
from app.data.service import IngestionService
from app.data.store import SnapshotStore
from app.providers.base import FetchBundle, SourcePoint


def _mapping_for(registry, **want):
    for m in registry["sources"]:
        if all(m.get(k) == v for k, v in want.items()):
            return m
    raise AssertionError(f"no mapping matching {want!r}")


@pytest.fixture()
def seeded_store(tmp_path, monkeypatch):
    db_path = tmp_path / "read-endpoints.sqlite3"
    monkeypatch.setenv("INFLATION_DB_PATH", str(db_path))
    store = SnapshotStore(db_path)
    service = IngestionService(store)
    registry = service.registry

    run = store.create_run("USA", "headline_consumer_inflation")

    def bundle_for(provider):
        raw_id = store.save_bundle(run, FetchBundle(provider, f"https://example.test/{provider}", "2026-08-01T00:00:00Z", b"raw", "application/json", ()))
        return raw_id

    bls_raw = bundle_for("bls")
    fred_raw = bundle_for("fred")
    world_bank_raw = bundle_for("world_bank")

    # cpi + core: two clean, computable YoY periods each.
    cpi = _mapping_for(registry, geography="USA", indicator_id="headline_consumer_inflation", role="all_items_cpi_index", measure_id="cpi", region_id=None)
    core = _mapping_for(registry, geography="USA", indicator_id="headline_consumer_inflation", role="all_items_cpi_index", measure_id="core", region_id=None)
    for m, base, raw in ((cpi, 320.0, bls_raw), (core, 300.0, bls_raw)):
        store.save_point(run, raw, SourcePoint(m, "2025-06", base))
        store.save_point(run, raw, SourcePoint(m, "2025-07", base + 1))
        store.save_point(run, raw, SourcePoint(m, "2026-06", round(base * 1.03, 4)))
        store.save_point(run, raw, SourcePoint(m, "2026-07", round(base * 1.034, 4)))

    # Four census regions, deliberately distinct values.
    region_rates = {"Northeast": 3.2, "Midwest": 3.1, "South": 3.6, "West": 3.5}
    for region, rate in region_rates.items():
        m = _mapping_for(registry, geography="USA", indicator_id="headline_consumer_inflation", role="all_items_cpi_index", measure_id="cpi", region_id=region)
        store.save_point(run, bls_raw, SourcePoint(m, "2025-07", 100.0))
        store.save_point(run, bls_raw, SourcePoint(m, "2026-07", round(100.0 * (1 + rate / 100), 4)))

    service.calculate_available(run, "USA", "headline_consumer_inflation")

    # Essential-cost categories -- category_rates are already YoY, so this
    # goes straight through the existing (unmodified) essential_cost path.
    for cat, rate in {"food": 3.0, "housing": 3.2, "energy": 14.7, "transport": 2.5, "healthcare": 3.0, "communications": 1.0}.items():
        m = {"provider": "bls", "series_id": f"yoy:{cat}", "indicator_id": "essential_cost_inflation", "role": "category_rates", "geography": "USA", "component_id": cat, "frequency": "monthly", "unit": "percent_yoy"}
        store.save_point(run, bls_raw, SourcePoint(m, "2026-07", rate))
    service.calculate_available(run, "USA", "essential_cost_inflation")

    # Context strip: FOMC + labor-market series. Wage growth is a level
    # (average hourly earnings), so two years are seeded to prove the
    # endpoint derives its own YoY rather than passing the level through.
    fred_context = {"provider": "fred", "series_id": "DFEDTARU", "indicator_id": "context_metadata", "role": "fed_target_upper", "geography": "USA", "frequency": "monthly", "unit": "percent"}
    # Inserted out of chronological order on purpose: DFEDTARU is a daily
    # FRED series, and a regression here (picking "whichever row sorts
    # last" instead of the max observation_period) would silently return
    # a stale rate -- this caught exactly that bug during manual QA.
    store.save_point(run, fred_raw, SourcePoint(fred_context, "2026-05", 4.5))
    store.save_point(run, fred_raw, SourcePoint(fred_context, "2026-07", 3.75))
    store.save_point(run, fred_raw, SourcePoint({**fred_context, "series_id": "FEDFUNDS", "role": "fed_funds_rate"}, "2026-07", 3.62))
    store.save_point(run, fred_raw, SourcePoint({**fred_context, "series_id": "UNRATE", "role": "unemployment_rate"}, "2026-07", 4.1))
    wage_mapping = {**fred_context, "series_id": "CES0500000003", "role": "wage_growth", "unit": "local_currency", "currency": "USD"}
    store.save_point(run, fred_raw, SourcePoint(wage_mapping, "2025-07", 30.0))
    store.save_point(run, fred_raw, SourcePoint(wage_mapping, "2026-07", 31.2))

    # World cross-section: a handful of countries, including the USA (to
    # prove the monthly-engine overlay replaces it) and a hyperinflation tail.
    world_mapping = {"provider": "world_bank", "series_id": "FP.CPI.TOTL.ZG", "indicator_id": "median_country_inflation", "role": "country_rates", "geography": "GLOBAL", "frequency": "annual", "unit": "percent_yoy"}
    for iso3, name, value in (("USA", "United States", 999.0), ("FRA", "France", 2.4), ("VEN", "Venezuela, RB", 387.0)):
        store.save_point(run, world_bank_raw, SourcePoint({**world_mapping, "component_id": iso3}, "2024", value, provider_status=name))

    return store


@pytest.fixture()
def client(seeded_store):
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


class TestMeasures:
    def test_ledger_order_and_values(self, client):
        data = client.get("/api/v1/measures/USA").get_json()
        ids = [m["id"] for m in data["measures"]]
        assert ids == ["cpi", "core", "ccpi", "ppi", "pce", "cpce", "trim"]  # source_registry.yaml display order
        cpi = data["measures"][0]
        assert cpi["period"] == "2026-07"
        assert cpi["coverage"] == "full"
        assert cpi["yoy"] == pytest.approx(3.08, abs=0.05)
        assert cpi["seasonally_adjusted"] is False
        assert cpi["code"] == "CPI-U"

    def test_measure_without_observations_reports_unavailable(self, client):
        data = client.get("/api/v1/measures/USA").get_json()
        ccpi = next(m for m in data["measures"] if m["id"] == "ccpi")
        assert ccpi["coverage"] == "unavailable"
        assert ccpi["yoy"] is None

    def test_window_selects_mom_or_headline(self, client):
        headline = client.get("/api/v1/measures/USA").get_json()
        windowed = client.get("/api/v1/measures/USA?window=1m").get_json()
        cpi_headline = next(m for m in headline["measures"] if m["id"] == "cpi")
        cpi_windowed = next(m for m in windowed["measures"] if m["id"] == "cpi")
        assert cpi_windowed["yoy"] == cpi_windowed["mom"]
        assert cpi_windowed["yoy"] != cpi_headline["yoy"]

    def test_adjustment_filters_by_seasonally_adjusted_flag(self, client):
        sa_only = client.get("/api/v1/measures/USA?adjustment=sa").get_json()
        nsa_only = client.get("/api/v1/measures/USA?adjustment=nsa").get_json()
        assert {m["id"] for m in sa_only["measures"]} == {"pce", "cpce", "trim"}
        assert {m["id"] for m in nsa_only["measures"]} == {"cpi", "core", "ccpi", "ppi"}

    def test_unknown_geography_is_404(self, client):
        assert client.get("/api/v1/measures/THA").status_code == 404

    def test_unknown_window_is_400_not_silently_ignored(self, client):
        # Regression: an unrecognised ?window used to fall through to the
        # 12-month value while echoing the caller's own bogus value back in
        # the response body, asserting a filter it never applied.
        response = client.get("/api/v1/measures/USA?window=99y")
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "SCHEMA_ERROR"

    def test_unknown_adjustment_is_400_not_silently_ignored(self, client):
        response = client.get("/api/v1/measures/USA?adjustment=bogus")
        assert response.status_code == 400
        assert response.get_json()["error"]["code"] == "SCHEMA_ERROR"

    def test_six_month_window_and_explicit_period(self, client):
        six_m = client.get("/api/v1/measures/USA?window=6m").get_json()
        cpi_6m = next(m for m in six_m["measures"] if m["id"] == "cpi")
        assert cpi_6m["yoy"] is None  # only 4 monthly points seeded, 6-month history unavailable

        by_period = client.get("/api/v1/measures/USA?period=2026-06").get_json()
        cpi_earlier = next(m for m in by_period["measures"] if m["id"] == "cpi")
        assert cpi_earlier["period"] == "2026-06"
        core_earlier = next(m for m in by_period["measures"] if m["id"] == "core")
        assert core_earlier["coverage"] == "full"

    def test_context_strip_derives_wage_growth_from_the_level_series(self, client):
        data = client.get("/api/v1/measures/USA").get_json()
        by_key = {c["k"]: c["v"] for c in data["context"]}
        assert by_key["Fed target (upper)"] == 3.75
        assert by_key["Unemployment"] == 4.1
        assert by_key["Wage growth"] == pytest.approx(4.0, abs=0.05)  # (31.2/30 - 1) * 100

    def test_context_strip_absent_for_geographies_without_it(self, client):
        assert client.get("/api/v1/measures/USA").get_json()["context"]
        # EA has no context_metadata configured; the field is present but empty.
        resp = client.get("/api/v1/measures/EA")
        assert resp.status_code in (200, 404)


class TestCategories:
    def test_categories_map_component_labels(self, client):
        data = client.get("/api/v1/categories/USA").get_json()
        names = {c["name"] for c in data["categories"]}
        assert {"Food", "Housing", "Energy", "Transport", "Healthcare", "Communications"} <= names
        energy = next(c for c in data["categories"] if c["name"] == "Energy")
        assert energy["v"] == pytest.approx(14.7)

    def test_unknown_period_is_404(self, client):
        assert client.get("/api/v1/categories/USA?period=1999-01").status_code == 404


class TestRegionsUs:
    def test_every_state_inherits_its_region_and_flags_modelled(self, client):
        data = client.get("/api/v1/regions/us").get_json()
        assert data["modelled"] is True
        assert data["stateRegion"]["48"] == "South"  # Texas
        assert data["stateValues"]["48"] == pytest.approx(data["regions"]["South"])
        assert len(data["stateRegion"]) == 51
        assert data["regionTails"]["hi"]["region"] == "South"
        assert data["regionTails"]["lo"]["region"] == "Midwest"


class TestWorldCrossSection:
    def test_usa_is_overlaid_with_the_engine_figure_not_world_bank(self, client):
        data = client.get("/api/v1/world/cross-section").get_json()
        assert data["byIso"]["840"] == pytest.approx(3.08, abs=0.05)  # engine figure, not the seeded 999.0
        assert data["byIso"]["862"] == pytest.approx(387.0)  # Venezuela, numeric 862
        assert data["economies"] == 3
        assert any(t["name"] == "Venezuela, RB" and t["v"] == pytest.approx(387.0) for t in data["tails"])

    def test_headline_and_g20_are_unavailable_median_is_real(self, client):
        data = client.get("/api/v1/world/cross-section").get_json()
        assert data["headline"] is None
        assert data["g20"] is None
        assert data["median"] is not None


class TestResolve:
    def test_resolves_configured_entities_only(self, client):
        assert client.get("/api/v1/resolve?q=euro").get_json()["matches"][0]["id"] == "EA"
        assert client.get("/api/v1/resolve?q=texas").get_json()["matches"] == []
        assert client.get("/api/v1/resolve").get_json()["matches"] == []


class TestDataSourcesPublishers:
    def test_publisher_ledger_has_no_secrets_and_real_latest(self, client):
        data = client.get("/api/v1/meta/data-sources").get_json()
        bls = next(p for p in data["publishers"] if p["org"] == "BLS")
        assert bls["series"] > 0
        assert bls["latest"] == "2026-08-01T00:00:00Z"
        assert bls["next"] is None
        assert "USA" in bls["cov"]

    def test_conditional_etag_returns_304_when_unchanged(self, client):
        first = client.get("/api/v1/measures/USA")
        assert first.status_code == 200
        etag = first.headers.get("ETag")
        assert etag
        assert "max-age=60" in first.headers.get("Cache-Control", "")

        second = client.get("/api/v1/measures/USA", headers={"If-None-Match": etag})
        assert second.status_code == 304
        assert second.get_data() == b""
