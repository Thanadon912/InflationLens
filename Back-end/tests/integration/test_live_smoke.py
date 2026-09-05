"""Read-only smoke tests against the real official provider APIs.

Every other test in this suite mocks the network (via httpx.MockTransport
in test_live_data_pipeline.py), which is correct for testing our own
logic quickly and deterministically -- but it also means nothing detects
when BLS, FRED, BEA, Eurostat, ECB, or World Bank change their response
envelope in production. These tests exist for exactly that: one call per
provider, asserting only the envelope shape each adapter in
app/providers/adapters.py depends on (not specific values, which drift
with every real data release).

All tests are marked `live` and excluded from the default run
(pyproject.toml's `addopts = -m "not live"`) -- they make real outbound
HTTP requests, so they belong in a scheduled/nightly job, not a PR gate.
Run explicitly with: pytest -m live tests/integration/test_live_smoke.py
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from app.data.service import load_local_env
from app.providers.adapters import fetch_provider
from app.providers.base import ResilientClient

pytestmark = pytest.mark.live

load_local_env()

START_YEAR = datetime.now(UTC).year - 1


@pytest.fixture()
def client():
    c = ResilientClient(timeout=30.0, attempts=2)
    yield c
    c.client.close()


def test_bls_live_smoke(client):
    # BLS needs no API key. CUUR0000SA0 is the headline CPI-U series this
    # project already depends on (source_registry.yaml).
    mapping = {"provider": "bls", "series_id": "CUUR0000SA0", "indicator_id": "headline_consumer_inflation", "role": "all_items_cpi_index", "geography": "USA", "frequency": "monthly", "unit": "index"}
    bundles = fetch_provider("bls", [mapping], start_year=START_YEAR, client=client)
    assert bundles
    assert bundles[0].provider == "bls"
    assert bundles[0].points, "BLS returned zero observations for a live headline CPI series"
    assert all(isinstance(p.value, float) for p in bundles[0].points)


@pytest.mark.skipif(not os.environ.get("FRED_API_KEY"), reason="FRED_API_KEY not configured")
def test_fred_live_smoke(client):
    mapping = {"provider": "fred", "series_id": "CPIAUCNS", "indicator_id": "headline_consumer_inflation", "role": "shadow_index", "geography": "USA", "frequency": "monthly", "unit": "index"}
    bundles = fetch_provider("fred", [mapping], start_year=START_YEAR, client=client)
    assert bundles
    assert bundles[0].provider == "fred"
    assert bundles[0].points


@pytest.mark.skipif(not os.environ.get("BEA_API_KEY"), reason="BEA_API_KEY not configured")
def test_bea_live_smoke(client):
    # NIPA:T10105:1 (nominal GDP) is a real mapping this project depends on
    # (source_registry.yaml) -- unlike a fabricated table/line, BEA
    # actually publishes this one on every release.
    mapping = {"provider": "bea", "dataset": "NIPA", "table": "T10105", "line": "1", "series_id": "NIPA:T10105:1", "indicator_id": "economy_wide_inflation", "role": "nominal_gdp", "geography": "USA", "frequency": "quarterly", "unit": "local_currency"}
    bundles = fetch_provider("bea", [mapping], start_year=START_YEAR, client=client)
    assert bundles
    assert bundles[0].provider == "bea"
    assert bundles[0].points, "BEA returned zero observations for a live NIPA GDP series"


def test_eurostat_live_smoke(client):
    # Euro-area headline HICP -- no API key required.
    mapping = {
        "provider": "eurostat", "dataset": "prc_hicp_minr", "series_id": "prc_hicp_minr:M:I25:TOTAL:EA20",
        "indicator_id": "headline_consumer_inflation", "role": "all_items_cpi_index", "geography": "EA",
        "frequency": "monthly", "unit": "index",
        "filters": {"freq": "M", "unit": "I25", "coicop18": "TOTAL", "geo": "EA20"},
    }
    bundles = fetch_provider("eurostat", [mapping], start_year=START_YEAR, client=client)
    assert bundles
    assert bundles[0].provider == "eurostat"
    assert bundles[0].points


def test_ecb_live_smoke(client):
    # Euro-area M3 -- no API key required.
    mapping = {
        "provider": "ecb", "dataflow": "BSI", "series_id": "M.U2.Y.V.M30.X.1.U2.2300.Z01.E",
        "indicator_id": "broad_money_expansion", "role": "money_level", "geography": "EA",
        "frequency": "monthly", "unit": "local_currency", "currency": "EUR",
    }
    bundles = fetch_provider("ecb", [mapping], start_year=START_YEAR, client=client)
    assert bundles
    assert bundles[0].provider == "ecb"
    assert bundles[0].points


def test_world_bank_live_smoke(client):
    # World population -- no API key required.
    mapping = {"provider": "world_bank", "series_id": "SP.POP.TOTL", "indicator_id": "geography_metadata", "role": "population", "geography": "USA", "frequency": "annual", "unit": "persons"}
    bundles = fetch_provider("world_bank", [mapping], start_year=START_YEAR, client=client)
    assert bundles
    assert bundles[0].provider == "world_bank"
    assert any(b.points for b in bundles)
