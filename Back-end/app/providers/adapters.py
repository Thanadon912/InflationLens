from __future__ import annotations

import csv
import io
import os
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from app.providers.base import FetchBundle, ProviderError, ProviderSchemaError, ResilientClient, SourcePoint, json_bytes, sanitize_url, utc_now

BLS_URL = "https://api.bls.gov/publicAPI/v1/timeseries/data/"
FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
BEA_URL = "https://apps.bea.gov/api/data/"
EUROSTAT_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
ECB_URL = "https://data-api.ecb.europa.eu/service/data"
WORLD_BANK_URL = "https://api.worldbank.org/v2/country"


def fetch_provider(provider: str, mappings: list[dict[str, Any]], *, start_year: int, client: ResilientClient) -> list[FetchBundle]:
    handlers = {
        "bls": _fetch_bls,
        "fred": _fetch_fred,
        "bea": _fetch_bea,
        "eurostat": _fetch_eurostat,
        "ecb": _fetch_ecb,
        "world_bank": _fetch_world_bank,
    }
    if provider not in handlers:
        raise ProviderError(f"Unsupported provider {provider!r}")
    return handlers[provider](mappings, start_year=start_year, client=client)


def _fetch_bls(mappings, *, start_year, client):
    bundles = []
    for offset in range(0, len(mappings), 25):
        batch = mappings[offset : offset + 25]
        response = client.request("POST", BLS_URL, json={"seriesid": [m["series_id"] for m in batch], "startyear": str(start_year), "endyear": str(datetime.now(UTC).year)})
        body, data = json_bytes(response)
        if data.get("status") != "REQUEST_SUCCEEDED":
            raise ProviderSchemaError(f"BLS request failed: {data.get('message')}")
        by_id = {m["series_id"]: m for m in batch}
        points = []
        for series in data.get("Results", {}).get("series", []):
            mapping = by_id.get(series.get("seriesID"))
            if mapping is None:
                raise ProviderSchemaError("BLS returned an unrequested series")
            for item in series.get("data", []):
                period_code = item.get("period", "")
                if not (period_code.startswith("M") and period_code[1:].isdigit() and 1 <= int(period_code[1:]) <= 12):
                    continue
                if item.get("value") in {None, "", "-"}:
                    continue
                notes = " ".join(note.get("text", "") for note in item.get("footnotes", []) if note)
                points.append(SourcePoint(mapping, f"{item['year']}-{int(period_code[1:]):02d}", _number(item["value"]), is_estimated="preliminary" in notes.lower(), provider_status=notes or None))
        bundles.append(FetchBundle("bls", BLS_URL, utc_now(), body, response.headers.get("content-type", "application/json"), tuple(points)))
    return bundles


def _fetch_fred(mappings, *, start_year, client):
    key = _secret("FRED_API_KEY")
    bundles = []
    for mapping in mappings:
        params = {"series_id": mapping["series_id"], "api_key": key, "file_type": "json", "observation_start": f"{start_year}-01-01"}
        url = f"{FRED_URL}?{urlencode(params)}"
        response = client.request("GET", url)
        body, data = json_bytes(response)
        points = [SourcePoint(mapping, item["date"][:7], _number(item["value"]), data_vintage=item.get("realtime_end")) for item in data.get("observations", []) if item.get("value") not in {None, "."}]
        bundles.append(FetchBundle("fred", sanitize_url(url), utc_now(), body, response.headers.get("content-type", "application/json"), tuple(points)))
    return bundles


def _fetch_bea(mappings, *, start_year, client):
    key = _secret("BEA_API_KEY")
    bundles = []
    for mapping in mappings:
        params = {"UserID": key, "method": "GETDATA", "datasetname": mapping["dataset"], "TableName": mapping["table"], "Frequency": "Q", "Year": ",".join(str(year) for year in range(start_year, datetime.now(UTC).year + 1)), "ResultFormat": "JSON"}
        url = f"{BEA_URL}?{urlencode(params)}"
        response = client.request("GET", url)
        body, data = json_bytes(response)
        api = data.get("BEAAPI", {})
        if api.get("Error"):
            raise ProviderSchemaError(f"BEA error: {api['Error']}")
        rows = api.get("Results", {}).get("Data", [])
        points = []
        for row in rows:
            if str(row.get("LineNumber")) != str(mapping["line"]):
                continue
            raw_period = row["TimePeriod"]
            points.append(SourcePoint(mapping, raw_period.replace("Q", "-Q"), _number(row["DataValue"]), data_vintage=api.get("Results", {}).get("Notes", [{}])[0].get("NoteText") if api.get("Results", {}).get("Notes") else None))
        bundles.append(FetchBundle("bea", sanitize_url(url), utc_now(), body, response.headers.get("content-type", "application/json"), tuple(points)))
    return bundles


def _fetch_eurostat(mappings, *, start_year, client):
    bundles = []
    for mapping in mappings:
        params = {"lang": "en", "sinceTimePeriod": str(start_year), **mapping["filters"]}
        url = f"{EUROSTAT_URL}/{mapping['dataset']}?{urlencode(params)}"
        response = client.request("GET", url)
        body, data = json_bytes(response)
        expected_dimension = "coicop18" if mapping["dataset"] == "prc_hicp_minr" else "na_item"
        if expected_dimension not in data.get("id", []) or data.get("size", [0]).count(0):
            raise ProviderSchemaError(f"Eurostat schema mismatch for {mapping['dataset']}: expected dimension {expected_dimension}")
        time_index = data.get("dimension", {}).get("time", {}).get("category", {}).get("index", {})
        values = data.get("value", {})
        statuses = data.get("status", {}) or {}
        points = []
        for period, position in time_index.items():
            raw = values.get(str(position), values.get(position))
            if raw is None:
                continue
            status = statuses.get(str(position), statuses.get(position))
            points.append(SourcePoint(mapping, period, _number(raw), is_estimated=status in {"e", "p", "u"}, data_vintage=data.get("updated"), provider_status=status))
        bundles.append(FetchBundle("eurostat", url, utc_now(), body, response.headers.get("content-type", "application/json"), tuple(points)))
    return bundles


def _fetch_ecb(mappings, *, start_year, client):
    bundles = []
    for mapping in mappings:
        params = {"startPeriod": f"{start_year}-01", "format": "csvdata"}
        url = f"{ECB_URL}/{mapping['dataflow']}/{mapping['series_id']}?{urlencode(params)}"
        response = client.request("GET", url, headers={"Accept": "text/csv"})
        body = response.content
        rows = list(csv.DictReader(io.StringIO(response.text)))
        required = {"KEY", "TIME_PERIOD", "OBS_VALUE", "OBS_STATUS", "UNIT"}
        if not rows or not required.issubset(rows[0]):
            raise ProviderSchemaError("ECB SDMX CSV schema mismatch")
        points = [SourcePoint(mapping, row["TIME_PERIOD"], _number(row["OBS_VALUE"]), is_estimated=row["OBS_STATUS"] in {"P", "E"}, provider_status=row["OBS_STATUS"]) for row in rows]
        bundles.append(FetchBundle("ecb", url, utc_now(), body, response.headers.get("content-type", "text/csv"), tuple(points)))
    return bundles


def _fetch_world_bank(mappings, *, start_year, client):
    bundles = []
    for mapping in mappings:
        geo = mapping.get("provider_geography", mapping["geography"])
        cross_section = bool(mapping.get("cross_section"))
        page = 1
        all_points = []
        while True:
            params = {"format": "json", "date": f"{start_year}:{datetime.now(UTC).year}", "per_page": 1000, "page": page}
            url = f"{WORLD_BANK_URL}/{geo}/indicator/{mapping['series_id']}?{urlencode(params)}"
            response = client.request("GET", url)
            body, data = json_bytes(response)
            if not isinstance(data, list) or len(data) != 2:
                raise ProviderSchemaError("World Bank response envelope changed")
            for item in data[1] or []:
                if item.get("value") is None:
                    continue
                if cross_section:
                    # geo="all" returns one row per economy *and* per
                    # region/income-group aggregate ("World", "OECD
                    # members", ...); aggregates report an empty
                    # countryiso3code rather than a real ISO 3166-1
                    # alpha-3 code, so requiring one here is what limits
                    # this to actual countries (joined onward via
                    # app/config/iso_numeric.yaml).
                    iso3 = item.get("countryiso3code")
                    if not iso3:
                        continue
                    point_mapping = {**mapping, "component_id": iso3}
                    all_points.append(SourcePoint(point_mapping, item["date"], _number(item["value"]), provider_status=(item.get("country") or {}).get("value") or None))
                else:
                    all_points.append(SourcePoint(mapping, item["date"], _number(item["value"]), provider_status=item.get("obs_status") or None))
            bundles.append(FetchBundle("world_bank", url, utc_now(), body, response.headers.get("content-type", "application/json"), tuple(all_points if page == data[0].get("pages", 1) else ())))
            if page >= data[0].get("pages", 1):
                break
            page += 1
    return bundles


def _number(value: Any) -> float:
    try:
        result = float(str(value).replace(",", ""))
    except (TypeError, ValueError) as exc:
        raise ProviderSchemaError(f"Provider numeric value is invalid: {value!r}") from exc
    if result != result or result in {float("inf"), float("-inf")}:
        raise ProviderSchemaError("Provider numeric value is non-finite")
    return result


def _secret(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ProviderError(f"Required environment variable {name} is not set")
    return value
