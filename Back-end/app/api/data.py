from __future__ import annotations

from collections import defaultdict
import hashlib
import re

from flask import Blueprint, jsonify, request

from app.api.schemas import SchemaError
from app.config.loader import (
    load_iso_numeric,
    load_methodology_versions,
    load_source_registry,
    load_us_regions,
)
from app.data.service import SUPPORTED_INDICATORS, decorate_snapshot
from app.data.store import SnapshotStore
from app.engines.shared.aggregation import unweighted_median
from app.engines.shared.growth import year_over_year

data_bp = Blueprint("data", __name__)


@data_bp.after_request
def _add_conditional_cache_headers(response):
    if request.method in ("GET", "HEAD") and response.status_code == 200:
        digest = hashlib.sha256(response.get_data()).hexdigest()[:32]
        response.set_etag(digest)
        response.headers.setdefault("Cache-Control", "public, max-age=60, must-revalidate")
        return response.make_conditional(request)
    return response

_VALID_WINDOWS = {"12m", "1m", "6m"}
_VALID_ADJUSTMENTS = {"as_published", "sa", "nsa"}


def _validate_choice(value: str, *, param: str, allowed: set[str]) -> None:
    if value not in allowed:
        raise SchemaError(
            f"Query parameter {param!r} must be one of {sorted(allowed)}, got {value!r}",
            param=param,
            value=value,
            allowed=sorted(allowed),
        )

# Static publisher metadata for the source ledger (GET /meta/data-sources).
# Everything dynamic (which series, which geographies, the actual latest
# fetch) is read from source_registry.yaml and the store below -- this only
# supplies what a provider mapping cannot: the publisher's own display name
# and homepage.
_PUBLISHERS = {
    "bls": {"org": "BLS", "full": "U.S. Bureau of Labor Statistics", "url": "https://www.bls.gov/cpi/"},
    "bea": {"org": "BEA", "full": "U.S. Bureau of Economic Analysis", "url": "https://www.bea.gov/data/personal-consumption-expenditures-price-index-excluding-food-and-energy"},
    "fred": {"org": "Federal Reserve (FRED)", "full": "Federal Reserve Bank of St. Louis", "url": "https://fred.stlouisfed.org"},
    "eurostat": {"org": "Eurostat", "full": "Statistical Office of the European Union", "url": "https://ec.europa.eu/eurostat"},
    "ecb": {"org": "ECB", "full": "European Central Bank", "url": "https://data.ecb.europa.eu"},
    "world_bank": {"org": "World Bank", "full": "World Bank Group", "url": "https://data.worldbank.org"},
}

# Entities the search endpoint can resolve. Kept deliberately small: the
# engine only calculates for USA and EA (app/config/country_profiles/), so
# resolving anything else would point the frontend at a dead end. See
# README.md "Backend integration", integration point 5.
_RESOLVABLE = (
    {
        "kind": "country",
        "id": "USA",
        "label": "United States",
        "aliases": ("usa", "us", "united states", "america", "u.s.", "u.s.a.", "united states of america"),
        "pattern": re.compile(r"\b(usa|us|united states|america|u\.s\.|u\.s\.a\.|united states of america)\b", re.IGNORECASE),
    },
    {
        "kind": "country",
        "id": "EA",
        "label": "Euro area",
        "aliases": ("ea", "eu", "euro area", "eurozone", "europe", "euro", "e.u.", "european union"),
        "pattern": re.compile(r"\b(ea|eu|euro area|eurozone|europe|euro|e\.u\.|european union)\b", re.IGNORECASE),
    },
)


def _matches_entity(q: str, entity: dict) -> bool:
    entity_id = entity["id"].lower()
    if q == entity_id or entity_id.startswith(q):
        return True
    label = entity["label"].lower()
    if q == label or q in label or label.startswith(q):
        return True
    for alias in entity["aliases"]:
        if q == alias or alias.startswith(q):
            return True
        if len(alias) >= 3 and alias in q:
            return True
    if entity["pattern"].search(q):
        return True
    return False


def _not_found(message: str):
    return jsonify({"error": {"code": "DATA_SNAPSHOT_NOT_FOUND", "message": message, "details": {}}}), 404


def _headline_mappings(geography: str, *, region_id=None):
    """Every headline_consumer_inflation all_items_cpi_index mapping for
    this geography, keyed by measure_id, in source_registry.yaml order
    (the ledger's display order)."""

    return {
        m["measure_id"]: m
        for m in load_source_registry()["sources"]
        if m["geography"] == geography and m["indicator_id"] == "headline_consumer_inflation" and m["role"] == "all_items_cpi_index" and m.get("region_id") == region_id and m.get("measure_id")
    }


def _component_value(result: dict, key: str):
    return next((c["value"] for c in result.get("components", []) if c["key"] == key), None)


def _windowed_value(result: dict, window: str):
    if window == "1m":
        return _component_value(result, "mom")
    if window == "6m":
        return _component_value(result, "six_month_annualized")
    return result["value"]


def _context_usa(store: SnapshotStore) -> list[dict]:
    """FOMC/labor-market context strip (source_registry.yaml's
    context_metadata mappings) -- pure passthrough of the latest published
    level for each series, except wage growth: CES0500000003 is an average
    hourly-earnings *level*, not a rate, so its YoY change is computed here
    with the same year_over_year() the engines use, not by the engine
    itself (context_metadata carries no IndicatorResult)."""

    # latest_observations() returns every stored period for every role --
    # fed_target_upper (DFEDTARU) in particular is a *daily* FRED series,
    # so "the row that happens to sort last" is not reliably "the latest
    # date". Reduce to the max observation_period per role explicitly.
    latest: dict[str, dict] = {}
    for row in store.latest_observations("USA", "context_metadata"):
        if row["role"] == "wage_growth":
            continue
        current = latest.get(row["role"])
        if current is None or row["observation_period"] > current["observation_period"]:
            latest[row["role"]] = row

    def level(role, label):
        row = latest.get(role)
        return {"k": label, "v": row["value"]} if row else None

    wage_rows = sorted(store.latest_observations("USA", "context_metadata", "wage_growth"), key=lambda r: r["observation_period"])
    wage_growth = None
    if wage_rows:
        by_period = {r["observation_period"]: r["value"] for r in wage_rows}
        latest_period = wage_rows[-1]["observation_period"]
        prior_period = f"{int(latest_period[:4]) - 1}{latest_period[4:]}"
        if prior_period in by_period:
            wage_growth = {"k": "Wage growth", "v": round(year_over_year(by_period[latest_period], by_period[prior_period]), 1)}

    return [item for item in (
        level("fed_target_upper", "Fed target (upper)"),
        level("fed_funds_rate", "Fed funds"),
        wage_growth,
        level("unemployment_rate", "Unemployment"),
    ) if item is not None]


@data_bp.get("/country/<geography>/<indicator_id>")
def cached_country_indicator(geography: str, indicator_id: str):
    if indicator_id not in SUPPORTED_INDICATORS:
        return _not_found(f"No cached-provider integration is configured for {indicator_id!r}")
    period = request.args.get("period", "latest")
    methodology_version = load_methodology_versions()["country"][indicator_id]
    row = SnapshotStore().get_result(geography.upper(), indicator_id, period, methodology_version=methodology_version)
    if row is None:
        return _not_found(f"No data snapshot for {geography.upper()}/{indicator_id}/{period}")
    return jsonify(decorate_snapshot(row, load_source_registry()["defaults"]))


@data_bp.get("/country/<geography>/dashboard")
def cached_country_dashboard(geography: str):
    period = request.args.get("period", "latest")
    store = SnapshotStore()
    defaults = load_source_registry()["defaults"]
    versions = load_methodology_versions()["country"]
    results = []
    for indicator_id in SUPPORTED_INDICATORS:
        row = store.get_result(geography.upper(), indicator_id, period, methodology_version=versions[indicator_id])
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
    coverage_by_provider: dict[str, set[str]] = defaultdict(set)
    series_by_provider: dict[str, set[str]] = defaultdict(set)
    for item in registry["sources"]:
        coverage_by_provider[item["provider"]].add(item["geography"])
        series_by_provider[item["provider"]].add(item["series_id"])
    latest_by_provider = SnapshotStore().latest_retrieval_by_provider()
    publishers = [
        {
            "org": meta["org"],
            "full": meta["full"],
            "url": meta["url"],
            "series": len(series_by_provider[provider]),
            "cov": ", ".join(sorted(coverage_by_provider[provider])),
            "latest": latest_by_provider.get(provider),
            # No release-calendar source is ingested; printing an invented
            # next-release date would fail the same honesty bar the rest
            # of this ledger holds every other figure to.
            "next": None,
        }
        for provider, meta in _PUBLISHERS.items()
        if provider in coverage_by_provider
    ]
    return jsonify({"config_version": registry["config_version"], "defaults": registry["defaults"], "sources": public_sources, "publishers": publishers})


@data_bp.get("/measures/<geography>")
def measures(geography: str):
    """The US price-measure ledger: seven series side by side (README.md
    "Backend integration", integration point 1). ?period defaults to each
    measure's own latest; ?window selects 12m/1m/6m annualised; ?adjustment
    filters to as_published (all)/sa/nsa."""

    geography = geography.upper()
    mappings = _headline_mappings(geography)
    if not mappings:
        return _not_found(f"No US-measure ledger is configured for {geography!r}")

    period = request.args.get("period", "latest")
    window = request.args.get("window", "12m")
    adjustment = request.args.get("adjustment", "as_published")
    _validate_choice(window, param="window", allowed=_VALID_WINDOWS)
    _validate_choice(adjustment, param="adjustment", allowed=_VALID_ADJUSTMENTS)

    store = SnapshotStore()
    defaults = load_source_registry()["defaults"]
    headline_version = load_methodology_versions()["country"]["headline_consumer_inflation"]
    if period == "latest":
        rows_by_measure = {
            row["measure_id"]: row
            for row in store.list_latest_results(
                geography,
                "headline_consumer_inflation",
                region_id=None,
                methodology_version=headline_version,
            )
        }
    else:
        rows_by_measure = {}
        for measure_id in mappings:
            row = store.get_result(
                geography,
                "headline_consumer_inflation",
                period,
                measure_id=measure_id,
                methodology_version=headline_version,
            )
            if row is not None:
                rows_by_measure[measure_id] = row

    out = []
    for measure_id, mapping in mappings.items():
        sa = mapping.get("seasonally_adjusted")
        if adjustment == "sa" and sa is not True:
            continue
        if adjustment == "nsa" and sa is not False:
            continue
        row = rows_by_measure.get(measure_id)
        base = {
            "id": measure_id,
            "code": mapping.get("measure_code", measure_id),
            "name": mapping.get("measure_name", measure_id),
            "note": mapping.get("measure_note"),
            "seasonally_adjusted": sa,
            "src": mapping["provider"],
        }
        if row is None:
            out.append({**base, "yoy": None, "mom": None, "period": None, "coverage": "unavailable", "confidence": "low", "is_estimated": False, "method": "unavailable"})
            continue
        result = decorate_snapshot(row, defaults)
        out.append({
            **base,
            "yoy": _windowed_value(result, window),
            "mom": _component_value(result, "mom"),
            "period": result["period"],
            "src": result["input_series"][0]["provider"] if result["input_series"] else mapping["provider"],
            "coverage": result["coverage"],
            "confidence": result["confidence"],
            "is_estimated": result["is_estimated"],
            "method": result["method"],
            "data_snapshot": result.get("data_snapshot"),
        })
    context = _context_usa(store) if geography == "USA" else []
    return jsonify({"geography": geography, "window": window, "adjustment": adjustment, "measures": out, "context": context})


@data_bp.get("/categories/<geography>")
def categories(geography: str):
    """CPI component ladder (README.md integration point 4): the essential-
    cost basket's category-level rates, already cached as
    essential_cost_inflation's components."""

    geography = geography.upper()
    period = request.args.get("period", "latest")
    essential_version = load_methodology_versions()["country"]["essential_cost_inflation"]
    row = SnapshotStore().get_result(geography, "essential_cost_inflation", period, methodology_version=essential_version)
    if row is None:
        return _not_found(f"No category data for {geography!r}/{period}")
    result = decorate_snapshot(row, load_source_registry()["defaults"])
    cats = [{"name": c["label"], "v": c["value"], "key": c["key"]} for c in result.get("components", []) if c["value"] is not None]
    return jsonify({"geography": geography, "period": result["period"], "categories": cats})


@data_bp.get("/regions/us")
def regions_us():
    """Census-region CPI and every state's inherited value (README.md
    integration point 3). No per-state estimate is computed -- states
    within a region share that region's published rate, and the modelled
    flag stays: attributing a whole region's index to one state is still
    an interpretive step, even though the number itself is official."""

    store = SnapshotStore()
    defaults = load_source_registry()["defaults"]
    regions_cfg = load_us_regions()
    headline_version = load_methodology_versions()["country"]["headline_consumer_inflation"]

    rows = store.list_latest_results(
        "USA",
        "headline_consumer_inflation",
        measure_id="cpi",
        methodology_version=headline_version,
    )
    region_rows = {row["region_id"]: row for row in rows if row["region_id"] is not None}

    regions_out: dict[str, float] = {}
    for region_name, row in region_rows.items():
        result = decorate_snapshot(row, defaults)
        if result["value"] is not None:
            regions_out[region_name] = result["value"]

    state_region: dict[str, str] = {}
    state_values: dict[str, float] = {}
    for region_name, fips_list in regions_cfg["regions"].items():
        for fips in fips_list:
            state_region[fips] = region_name
            if region_name in regions_out:
                state_values[fips] = regions_out[region_name]

    region_tails = None
    if regions_out:
        ranked = sorted(regions_out.items(), key=lambda kv: kv[1])
        region_tails = {"lo": {"region": ranked[0][0], "v": ranked[0][1]}, "hi": {"region": ranked[-1][0], "v": ranked[-1][1]}}

    return jsonify({
        "geography": "USA",
        "regions": regions_out,
        "regionTails": region_tails,
        "stateRegion": state_region,
        "stateValues": state_values,
        "stateNames": regions_cfg.get("state_names", {}),
        "modelled": True,
    })


@data_bp.get("/world/cross-section")
def world_cross_section():
    """World choropleth + hero aggregates (README.md integration point 2).
    Countries join world-atlas's numeric IDs via app/config/iso_numeric.yaml.
    USA is overlaid with the engine's own monthly figure rather than the
    annual World Bank one (docs/API_DATA_SOURCES_GUIDE.md section 7.1:
    "do not use annual World Bank CPI when current monthly official data
    exists"); EA has no single ISO-numeric feature to shade and is not
    part of this cross-section.

    `headline` and `g20` are not computed: both are population/GDP-PPP
    weighted aggregates (GLOBAL_INFLATION_METHODS.md), and this endpoint
    does not ingest population or GDP-PPP weights for ~190 economies.
    Rather than print an unweighted number under a weighted label, both
    are reported unavailable; `median` is genuinely unweighted by
    definition (median_country_inflation's own method), so it is real.
    """

    store = SnapshotStore()
    iso_numeric = load_iso_numeric()
    rows = store.latest_by_component("GLOBAL", "median_country_inflation", "country_rates")

    by_iso: dict[int, float] = {}
    countries = []
    for row in rows:
        iso3 = row["component_id"]
        numeric = iso_numeric.get(iso3)
        if numeric is None:
            continue
        by_iso[numeric] = row["value"]
        countries.append({"iso3": iso3, "numeric": numeric, "name": row["provider_status"] or iso3, "v": row["value"], "period": row["observation_period"]})

    headline_version = load_methodology_versions()["country"]["headline_consumer_inflation"]
    usa_row = store.get_result("USA", "headline_consumer_inflation", measure_id="cpi", methodology_version=headline_version)
    if usa_row is not None:
        usa_result = decorate_snapshot(usa_row, load_source_registry()["defaults"])
        if usa_result["value"] is not None:
            by_iso[840] = usa_result["value"]
            countries = [c for c in countries if c["iso3"] != "USA"]
            countries.append({"iso3": "USA", "numeric": 840, "name": "United States", "v": usa_result["value"], "period": usa_result["period"], "basis": "engine"})

    values = [c["v"] for c in countries]
    median_value = unweighted_median(values) if values else None
    tails = sorted(countries, key=lambda c: c["v"], reverse=True)[:4]

    return jsonify({
        "byIso": by_iso,
        "headline": None,
        "median": median_value,
        "g20": None,
        "economies": len(countries),
        "tails": [{"name": c["name"], "v": c["v"]} for c in tails],
    })


@data_bp.get("/resolve")
def resolve():
    """Entity-resolution search (README.md integration point 5). Resolves
    only what the engine actually covers -- USA and EA -- so a match is
    never a dead end; anything else returns an empty match list rather
    than a guess."""

    q = (request.args.get("q") or "").strip().lower()
    matches = []
    if q:
        for entity in _RESOLVABLE:
            if _matches_entity(q, entity):
                matches.append({"kind": entity["kind"], "id": entity["id"], "label": entity["label"]})
    return jsonify({"query": q, "matches": matches})
