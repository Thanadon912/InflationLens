import json

import httpx
import pytest

from app.providers.adapters import _number, fetch_provider
from app.providers.base import ProviderError, ProviderSchemaError, ResilientClient, json_bytes


def mapping(provider, **extra):
    return {"provider": provider, "series_id": "S", "indicator_id": "i", "role": "r", "geography": "USA", "frequency": "monthly", "unit": "index", **extra}


def client(handler):
    return ResilientClient(transport=httpx.MockTransport(handler), attempts=1, sleep=lambda _: None)


def test_unsupported_provider_and_numeric_guards():
    with pytest.raises(ProviderError):
        fetch_provider("unknown", [], start_year=2025, client=client(lambda r: httpx.Response(200)))
    with pytest.raises(ProviderSchemaError):
        _number("not-a-number")
    with pytest.raises(ProviderSchemaError):
        _number("nan")


def test_invalid_json_and_client_network_failure():
    response = httpx.Response(200, content=b"not-json")
    with pytest.raises(ProviderSchemaError):
        json_bytes(response)
    failing = ResilientClient(transport=httpx.MockTransport(lambda request: (_ for _ in ()).throw(httpx.ConnectError("offline", request=request))), attempts=1, sleep=lambda _: None)
    with pytest.raises(ProviderError):
        failing.request("GET", "https://example.test")
    failing.close()


def test_bls_status_and_unrequested_series_errors():
    m = mapping("bls")
    failed = client(lambda r: httpx.Response(200, json={"status": "REQUEST_FAILED", "message": ["bad"]}))
    with pytest.raises(ProviderSchemaError):
        fetch_provider("bls", [m], start_year=2025, client=failed)
    unknown = client(lambda r: httpx.Response(200, json={"status": "REQUEST_SUCCEEDED", "Results": {"series": [{"seriesID": "OTHER", "data": []}]}}))
    with pytest.raises(ProviderSchemaError):
        fetch_provider("bls", [m], start_year=2025, client=unknown)


def test_missing_fred_secret(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    with pytest.raises(ProviderError):
        fetch_provider("fred", [mapping("fred")], start_year=2025, client=client(lambda r: httpx.Response(200)))


def test_bea_error_ecb_schema_and_world_bank_envelope(monkeypatch):
    monkeypatch.setenv("BEA_API_KEY", "key")
    bea_mapping = mapping("bea", dataset="NIPA", table="T", line="1")
    with pytest.raises(ProviderSchemaError):
        fetch_provider("bea", [bea_mapping], start_year=2025, client=client(lambda r: httpx.Response(200, json={"BEAAPI": {"Error": {"APIErrorDescription": "bad"}}})))
    ecb_mapping = mapping("ecb", dataflow="BSI")
    with pytest.raises(ProviderSchemaError):
        fetch_provider("ecb", [ecb_mapping], start_year=2025, client=client(lambda r: httpx.Response(200, text="bad,csv\n1,2")))
    with pytest.raises(ProviderSchemaError):
        fetch_provider("world_bank", [mapping("world_bank")], start_year=2025, client=client(lambda r: httpx.Response(200, json={"changed": True})))


def test_world_bank_pagination_and_null_values():
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        page = int(request.url.params["page"])
        values = [{"date": str(2024 + page), "value": None if page == 1 else 10, "obs_status": ""}]
        return httpx.Response(200, json=[{"page": page, "pages": 2}, values])
    bundles = fetch_provider("world_bank", [mapping("world_bank")], start_year=2025, client=client(handler))
    assert calls == 2
    assert len(bundles) == 2
    assert bundles[-1].points[0].value == 10
