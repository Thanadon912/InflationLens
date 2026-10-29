from __future__ import annotations

import httpx
import pytest

from app import create_app
from app.api.rate_limit import SlidingWindowLimiter
from app.config.loader import ConfigError, load_country_profile
from app.data.service import IngestionService
from app.data.store import SnapshotStore
from app.providers.base import ProviderError, ResilientClient, sanitize_text, sanitize_url


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


class TestSlidingWindowLimiter:
    def test_enforces_limit_and_resets_after_window(self):
        now = 100.0
        limiter = SlidingWindowLimiter(window_seconds=60.0, max_clients=4, clock=lambda: now)

        allowed1, rem1, reset1 = limiter.check("calc", "10.0.0.1", 2)
        assert (allowed1, rem1, reset1) == (True, 1, 60)

        now = 115.0
        allowed2, rem2, reset2 = limiter.check("calc", "10.0.0.1", 2)
        assert (allowed2, rem2, reset2) == (True, 0, 45)

        allowed3, rem3, reset3 = limiter.check("calc", "10.0.0.1", 2)
        assert (allowed3, rem3, reset3) == (False, 0, 45)

        # Advance past the 60s window -> bucket resets
        now = 161.0
        allowed4, rem4, reset4 = limiter.check("calc", "10.0.0.1", 2)
        assert (allowed4, rem4, reset4) == (True, 1, 60)

    def test_bounded_client_eviction_and_reset(self):
        limiter = SlidingWindowLimiter(window_seconds=60.0, max_clients=2, clock=lambda: 0.0)
        limiter.check("read", "ip-1", 1)
        limiter.check("read", "ip-2", 1)
        # Adding ip-3 evicts ip-1 (oldest) so ip-1 gets a fresh quota
        limiter.check("read", "ip-3", 1)
        allowed_ip1, _, _ = limiter.check("read", "ip-1", 1)
        assert allowed_ip1 is True

        limiter.reset()
        allowed_ip3, _, _ = limiter.check("read", "ip-3", 1)
        assert allowed_ip3 is True


class TestFlaskRateLimitingAndSecurityHeaders:
    def test_security_headers_present_on_all_responses(self, client):
        ok = client.get("/api/v1/health")
        assert ok.headers["X-Content-Type-Options"] == "nosniff"
        assert ok.headers["X-Frame-Options"] == "DENY"
        assert ok.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert "default-src 'none'" in ok.headers["Content-Security-Policy"]
        assert "geolocation=()" in ok.headers["Permissions-Policy"]
        assert ok.headers["Cross-Origin-Resource-Policy"] == "cross-origin"

        not_found = client.get("/api/v1/nonexistent")
        assert not_found.status_code == 404
        assert not_found.headers["X-Content-Type-Options"] == "nosniff"

    def test_read_and_calc_rate_limits_and_exemptions(self):
        app = create_app()
        app.config.update(
            TESTING=True,
            RATE_LIMIT_ENABLED=True,
            RATE_LIMIT_READ_PER_MINUTE=2,
            RATE_LIMIT_CALC_PER_MINUTE=1,
        )
        with app.test_client() as c:
            # First two GET requests succeed with rate-limit headers
            r1 = c.get("/api/v1/meta/countries")
            assert r1.status_code == 200
            assert r1.headers["X-RateLimit-Limit"] == "2"
            assert r1.headers["X-RateLimit-Remaining"] == "1"

            r2 = c.get("/api/v1/meta/countries")
            assert r2.status_code == 200
            assert r2.headers["X-RateLimit-Remaining"] == "0"

            # Third GET request is throttled with 429
            r3 = c.get("/api/v1/meta/countries")
            assert r3.status_code == 429
            assert r3.headers["Retry-After"]
            assert r3.headers["X-RateLimit-Remaining"] == "0"
            body = r3.get_json()
            assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
            assert body["error"]["details"]["bucket"] == "read"

            # Health endpoint and OPTIONS preflight remain exempt even when read bucket is exhausted
            assert c.get("/api/v1/health").status_code == 200
            assert c.options("/api/v1/meta/countries").status_code == 200

            # POST uses separate 'calc' bucket (limit=1)
            p1 = c.post("/api/v1/country/USA/headline_consumer_inflation", json={})
            assert p1.status_code in {400, 422}
            assert p1.headers["X-RateLimit-Limit"] == "1"

            p2 = c.post("/api/v1/country/USA/headline_consumer_inflation", json={})
            assert p2.status_code == 429
            assert p2.get_json()["error"]["details"]["bucket"] == "calc"

    def test_x_forwarded_for_ignored_unless_trust_proxy_enabled(self):
        app = create_app()
        app.config.update(
            TESTING=True,
            RATE_LIMIT_ENABLED=True,
            RATE_LIMIT_READ_PER_MINUTE=1,
            TRUST_PROXY_HEADERS=False,
        )
        with app.test_client() as c:
            assert c.get("/api/v1/meta/countries", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
            # Spoofing a different X-Forwarded-For does NOT bypass the limit when TRUST_PROXY_HEADERS=False
            assert c.get("/api/v1/meta/countries", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429

        app.config["TRUST_PROXY_HEADERS"] = True
        app.extensions["rate_limiter"].reset()
        with app.test_client() as c:
            assert c.get("/api/v1/meta/countries", headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.1"}).status_code == 200
            assert c.get("/api/v1/meta/countries", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429
            assert c.get("/api/v1/meta/countries", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 200
            # Empty X-Forwarded-For falls back to remote_addr
            assert c.get("/api/v1/meta/countries", headers={"X-Forwarded-For": "   "}).status_code == 200

    def test_rate_limit_disabled_flag(self):
        app = create_app()
        app.config.update(
            TESTING=True,
            RATE_LIMIT_ENABLED=False,
            RATE_LIMIT_READ_PER_MINUTE=1,
        )
        with app.test_client() as c:
            assert c.get("/api/v1/meta/countries").status_code == 200
            assert c.get("/api/v1/meta/countries").status_code == 200
            assert "X-RateLimit-Limit" not in c.get("/api/v1/meta/countries").headers


class TestPathTraversalAndSecretSanitization:
    @pytest.mark.parametrize("malicious_geo", ["../global_weights", "../../etc/passwd", "USA/../../secret", "A", "TOO_LONG_GEOGRAPHY_CODE_12345"])
    def test_load_country_profile_rejects_traversal_and_invalid_codes(self, malicious_geo):
        with pytest.raises(ConfigError) as exc_info:
            load_country_profile(malicious_geo)
        assert "/" not in str(exc_info.value).replace(malicious_geo, "")

    def test_unknown_country_404_does_not_leak_filesystem_path(self, client):
        r = client.get("/api/v1/meta/config/country/ZZZ")
        assert r.status_code == 404
        msg = r.get_json()["error"]["message"]
        assert "country_profiles" not in msg
        assert ".yaml" not in msg

    def test_sanitize_url_and_sanitize_text_redact_credentials(self):
        raw_url = "https://api.stlouisfed.org/fred/series/observations?series_id=M2SL&api_key=SUPER_SECRET_123&file_type=json"
        assert "SUPER_SECRET_123" not in sanitize_url(raw_url)
        assert "api_key=REDACTED" in sanitize_url(raw_url)

        err_msg = f"Transport failed for {raw_url} and UserID=BEA_SECRET_999"
        cleaned = sanitize_text(err_msg)
        assert "SUPER_SECRET_123" not in cleaned
        assert "BEA_SECRET_999" not in cleaned
        assert "api_key=REDACTED" in cleaned
        assert "UserID=REDACTED" in cleaned

    def test_resilient_client_refuses_non_https_urls(self):
        rc = ResilientClient(transport=httpx.MockTransport(lambda r: httpx.Response(200)), attempts=1)
        try:
            with pytest.raises(ProviderError, match="Refusing non-HTTPS provider URL"):
                rc.request("GET", "http://api.stlouisfed.org/fred/series")
            with pytest.raises(ProviderError, match="Refusing non-HTTPS provider URL"):
                rc.request("GET", "file:///etc/passwd")
        finally:
            rc.close()

    def test_store_and_service_redact_secrets_in_issues_and_verify(self, tmp_path, monkeypatch):
        store = SnapshotStore(tmp_path / "sec.sqlite3")
        run_id = store.create_run("USA", "broad_money_expansion")
        store.add_issue(run_id, "PROVIDER_FETCH_FAILED", "Failed GET https://example.test?api_key=LEAKED_KEY_1&series=M2")
        issues = store.issues(run_id)
        assert "LEAKED_KEY_1" not in issues[0]["message"]
        assert "api_key=REDACTED" in issues[0]["message"]

        monkeypatch.setenv("FRED_API_KEY", "LEAKED_FRED_SECRET")
        failing_client = ResilientClient(
            transport=httpx.MockTransport(
                lambda req: (_ for _ in ()).throw(RuntimeError(f"boom on {req.url}"))
            ),
            attempts=1,
        )
        svc = IngestionService(store=store, client=failing_client)
        verify_out = svc.verify(geography="USA", indicator="broad_money_expansion")
        for check in verify_out["checks"]:
            assert "LEAKED_FRED_SECRET" not in check.get("error", "")
        failing_client.close()
