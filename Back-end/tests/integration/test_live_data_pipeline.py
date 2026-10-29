import json
from datetime import date
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app import create_app
from app.data.service import IngestionService
from app.data.store import SnapshotStore
from app.providers.base import ProviderError, ProviderSchemaError, ResilientClient, sanitize_url


def _months():
    return [f"2025-{m:02d}" for m in range(1, 13)] + [f"2026-{m:02d}" for m in range(1, 5)]


def _eurostat(periods, values, *, dataset, status=None):
    dimension = "coicop18" if dataset == "prc_hicp_minr" else "na_item"
    return {
        "id": ["freq", "unit", dimension, "geo", "time"],
        "size": [1, 1, 1, 1, len(periods)],
        "updated": "2026-04-30T11:00:00+0200",
        "dimension": {"time": {"category": {"index": {p: i for i, p in enumerate(periods)}}}},
        "value": {str(i): value for i, value in enumerate(values)},
        **({"status": status} if status else {}),
    }


@pytest.fixture()
def provider_transport(monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "fred-secret")
    monkeypatch.setenv("BEA_API_KEY", "bea-secret")

    def handler(request: httpx.Request):
        host, path = request.url.host, request.url.path
        if host == "api.bls.gov":
            requested = json.loads(request.content)["seriesid"]
            series = []
            for series_id in requested:
                data = []
                for i, period in enumerate(_months()):
                    year, month = period.split("-")
                    data.append({"year": year, "period": f"M{month}", "value": str(100 + i), "footnotes": [{"text": "Preliminary."}] if period == "2026-04" else [{}]})
                data.append({"year": "2026", "period": "M13", "value": "115", "footnotes": [{}]})
                data.append({"year": "2026", "period": "M05", "value": "-", "footnotes": [{}]})
                series.append({"seriesID": series_id, "data": list(reversed(data))})
            return httpx.Response(200, json={"status": "REQUEST_SUCCEEDED", "message": [], "Results": {"series": series}})
        if host == "api.stlouisfed.org":
            series_id = request.url.params["series_id"]
            values = [100 + i + (0.02 if series_id == "CPIAUCNS" else 0) for i in range(len(_months()))]
            if series_id == "M2SL":
                values = [20000 + i * 100 for i in range(len(_months()))]
            observations = [{"date": f"{period}-01", "value": str(value), "realtime_end": "2026-05-01"} for period, value in zip(_months(), values)]
            return httpx.Response(200, json={"observations": observations})
        if host == "apps.bea.gov":
            params = {key.lower(): value for key, value in request.url.params.multi_items()}
            table = params["tablename"]
            base = 30000 if table == "T10105" else 24000
            rows = [{"LineNumber": "1", "TimePeriod": period, "DataValue": f"{base + i * 100:,}"} for i, period in enumerate(("2025Q1", "2025Q2", "2026Q1", "2026Q2"))]
            rows.append({"LineNumber": "2", "TimePeriod": "2026Q1", "DataValue": "1"})
            return httpx.Response(200, json={"BEAAPI": {"Results": {"Data": rows, "Notes": [{"NoteText": "vintage"}]}}})
        if host == "ec.europa.eu":
            dataset = path.rsplit("/", 1)[-1]
            if dataset == "prc_hicp_minr":
                periods = _months()
                return httpx.Response(200, json=_eurostat(periods, [100 + i for i in range(len(periods))], dataset=dataset, status={str(len(periods) - 1): "e"}))
            periods = ["2025-Q1", "2025-Q2", "2026-Q1", "2026-Q2"]
            unit = request.url.params["unit"]
            base = 30000 if unit == "CP_MEUR" else 24000
            return httpx.Response(200, json=_eurostat(periods, [base + i * 100 for i in range(4)], dataset=dataset))
        if host == "data-api.ecb.europa.eu":
            csv_body = "KEY,TIME_PERIOD,OBS_VALUE,OBS_STATUS,UNIT\n" + "\n".join(f"BSI.KEY,{p},{17000000+i*10000},{'P' if p == '2026-04' else 'A'},EUR" for i, p in enumerate(_months()))
            return httpx.Response(200, text=csv_body, headers={"content-type": "text/csv"})
        if host == "api.worldbank.org":
            return httpx.Response(200, json=[{"page": 1, "pages": 1}, [{"date": "2025", "value": 1000000, "obs_status": ""}]])
        raise AssertionError(f"unexpected URL {request.url}")

    return httpx.MockTransport(handler)


@pytest.fixture()
def synced_store(tmp_path, monkeypatch, provider_transport):
    db_path = tmp_path / "pipeline.sqlite3"
    monkeypatch.setenv("INFLATION_DB_PATH", str(db_path))
    store = SnapshotStore(db_path)
    client = ResilientClient(transport=provider_transport, sleep=lambda _: None)
    result = IngestionService(store, client).sync()
    assert result["status"] == "success", result
    return store, result


def test_full_provider_pipeline_calculates_eight_cached_views(synced_store):
    store, result = synced_store
    assert result["successes"] > 10
    for geography in ("USA", "EA"):
        for indicator in ("headline_consumer_inflation", "essential_cost_inflation", "broad_money_expansion", "economy_wide_inflation"):
            snapshot = store.get_result(geography, indicator)
            assert snapshot is not None, (geography, indicator)
            assert snapshot["result"]["methodology_version"] == "1.0.2"
            if indicator == "essential_cost_inflation":
                assert snapshot["period"] == "2026-04"
    assert any(issue["code"] == "CROSS_SOURCE_DIFFERENCE" for issue in result["issues"])
    assert store.status()["counts"]["raw_responses"] > 10


def test_cached_api_dashboard_status_issues_lineage_and_not_found(synced_store):
    store, result = synced_store
    app = create_app()
    app.config.update(TESTING=True)
    client = app.test_client()
    response = client.get("/api/v1/country/USA/headline_consumer_inflation?period=latest")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["data_snapshot"]["snapshot_id"]
    assert payload["is_estimated"] is True
    assert client.get("/api/v1/country/USA/dashboard").status_code == 200
    assert client.get("/api/v1/data/status").get_json()["latest_run"]["status"] == "success"
    assert client.get(f"/api/v1/data/issues?run_id={result['run_id']}").get_json()["issues"]
    lineage = client.get(f"/api/v1/data/lineage/{payload['data_snapshot']['snapshot_id']}")
    assert lineage.status_code == 200
    assert lineage.get_json()["raw_responses"]
    assert client.get("/api/v1/data/lineage/missing").status_code == 404
    assert client.get("/api/v1/country/USA/unsupported").status_code == 404
    assert client.get("/api/v1/country/THA/headline_consumer_inflation").status_code == 404
    unavailable = client.get("/api/v1/country/THA/dashboard").get_json()["indicators"]
    assert all(item["coverage"] == "unavailable" for item in unavailable)
    sources = client.get("/api/v1/meta/data-sources").get_json()
    assert sources["config_version"] == "source-registry-1.0.0"
    assert "fred-secret" not in json.dumps(sources)


def test_store_preserves_revisions_lineage_and_raw_hash(tmp_path):
    from app.providers.base import FetchBundle, SourcePoint

    store = SnapshotStore(tmp_path / "store.sqlite3")
    run = store.create_run("USA", "test")
    mapping = {"provider": "test", "series_id": "S", "indicator_id": "i", "role": "level", "geography": "USA", "frequency": "monthly", "unit": "index"}
    bundle = FetchBundle("test", "https://example.test/data", "2026-01-01T00:00:00Z", b"raw", "text/plain", (SourcePoint(mapping, "2025-01", 100),))
    raw_id = store.save_bundle(run, bundle)
    first = store.save_point(run, raw_id, bundle.points[0])
    second = store.save_point(run, raw_id, SourcePoint(mapping, "2025-01", 101), lineage=(first,))
    with store.connect() as db:
        revised = db.execute("SELECT is_revised FROM normalized_observations WHERE id=?", (second,)).fetchone()[0]
    assert revised == 1
    store.add_issue(run, "TEST", "message", details={"x": 1})
    store.finish_run(run, successes=1, failures=1)
    assert store.status()["latest_run"]["status"] == "partial"
    assert store.issues(run)[0]["details"] == {"x": 1}
    assert store.get_result("USA", "missing") is None
    assert store.lineage("missing") is None


def test_cli_status_reads_snapshot_store(synced_store):
    app = create_app()
    result = app.test_cli_runner().invoke(args=["data", "status"])
    assert result.exit_code == 0
    assert json.loads(result.output)["latest_run"]["status"] == "success"


def test_verify_does_not_write_database(tmp_path, monkeypatch, provider_transport):
    db_path = tmp_path / "verify.sqlite3"
    monkeypatch.setenv("INFLATION_DB_PATH", str(db_path))
    store = SnapshotStore(db_path)
    result = IngestionService(store, ResilientClient(transport=provider_transport, sleep=lambda _: None)).verify("USA", "headline_consumer_inflation")
    assert result["status"] == "ok"
    assert store.status()["counts"]["raw_responses"] == 0


def test_provider_failure_isolated_and_secret_not_persisted(tmp_path, monkeypatch):
    monkeypatch.setenv("FRED_API_KEY", "super-secret")
    monkeypatch.setenv("INFLATION_DB_PATH", str(tmp_path / "failure.sqlite3"))
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    service = IngestionService(client=ResilientClient(transport=transport, attempts=1, sleep=lambda _: None))
    result = service.sync("USA", "broad_money_expansion")
    assert result["status"] == "failed"
    assert "super-secret" not in json.dumps(result)
    assert service.store.status()["counts"]["raw_responses"] == 0


def test_http_retry_sanitization_and_schema_errors(monkeypatch):
    calls = 0
    def retry_handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(429, headers={"Retry-After": "0"}) if calls == 1 else httpx.Response(200, json={"ok": True})
    client = ResilientClient(transport=httpx.MockTransport(retry_handler), sleep=lambda _: None)
    assert client.request("GET", "https://example.test").json() == {"ok": True}
    assert calls == 2
    assert sanitize_url("https://x.test/a?api_key=secret&x=1") == "https://x.test/a?api_key=REDACTED&x=1"
    failing = ResilientClient(transport=httpx.MockTransport(lambda request: httpx.Response(400)), sleep=lambda _: None)
    with pytest.raises(ProviderError):
        failing.request("GET", "https://example.test")


def test_schema_drift_is_reported_without_publishing(tmp_path, monkeypatch):
    monkeypatch.setenv("INFLATION_DB_PATH", str(tmp_path / "drift.sqlite3"))
    def handler(request):
        return httpx.Response(200, json={"id": ["freq", "old_coicop", "time"], "size": [1, 1, 1], "dimension": {"time": {"category": {"index": {"2026-01": 0}}}}, "value": {"0": 100}})
    service = IngestionService(client=ResilientClient(transport=httpx.MockTransport(handler), sleep=lambda _: None))
    result = service.sync("EA", "headline_consumer_inflation")
    assert result["status"] == "failed"
    assert any(issue["code"] == "PROVIDER_FETCH_FAILED" for issue in result["issues"])
    assert service.store.status()["counts"]["indicator_results"] == 0


def test_cli_exit_codes_and_verify_output(monkeypatch, tmp_path):
    import app.data.cli as cli_module

    monkeypatch.setenv("INFLATION_DB_PATH", str(tmp_path / "cli.sqlite3"))
    app = create_app()
    runner = app.test_cli_runner()

    class FakeService:
        status = "success"
        def sync(self, geography, indicator):
            return {"status": self.status, "run_id": "r", "successes": 1, "failures": 0}
        def verify(self, geography, indicator):
            return {"status": self.status, "checks": []}

    fake = FakeService()
    monkeypatch.setattr(cli_module, "IngestionService", lambda: fake)
    assert runner.invoke(args=["data", "sync", "--geography", "USA"]).exit_code == 0
    fake.status = "partial"
    assert runner.invoke(args=["data", "sync"]).exit_code == 2
    assert runner.invoke(args=["data", "verify"]).exit_code == 2
    fake.status = "failed"
    assert runner.invoke(args=["data", "sync"]).exit_code == 1


def test_load_local_env_and_verify_failure(tmp_path, monkeypatch):
    from app.data.service import load_local_env

    env = tmp_path / ".env"
    env.write_text("# comment\nTEST_DATA_KEY=value\nNO_EQUALS\n", encoding="utf-8")
    monkeypatch.delenv("TEST_DATA_KEY", raising=False)
    load_local_env(env)
    assert __import__("os").environ["TEST_DATA_KEY"] == "value"

    monkeypatch.setenv("INFLATION_DB_PATH", str(tmp_path / "verify-fail.sqlite3"))
    transport = httpx.MockTransport(lambda request: httpx.Response(500))
    result = IngestionService(client=ResilientClient(transport=transport, attempts=1, sleep=lambda _: None)).verify("EA", "headline_consumer_inflation")
    assert result["status"] == "partial"
    assert result["checks"][0]["status"] == "failed"
