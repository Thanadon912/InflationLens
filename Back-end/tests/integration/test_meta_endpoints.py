class TestHealthAndMeta:
    def test_health(self, client):
        r = client.get("/api/v1/health")
        assert r.status_code == 200
        assert r.get_json() == {"status": "ok"}

    def test_indicators_lists_18(self, client):
        r = client.get("/api/v1/meta/indicators")
        data = r.get_json()
        assert len(data["country"]) == 10
        assert len(data["global"]) == 8

    def test_methodology_versions(self, client):
        r = client.get("/api/v1/meta/methodology")
        data = r.get_json()
        assert data["country"]["headline_consumer_inflation"] == "1.0.2"

    def test_global_weights_config(self, client):
        r = client.get("/api/v1/meta/global-weights")
        data = r.get_json()
        assert "coverage_thresholds" in data

    def test_countries_available(self, client):
        r = client.get("/api/v1/meta/countries")
        assert set(r.get_json()["available"]) >= {"USA", "EA", "THA"}

    def test_country_config(self, client):
        r = client.get("/api/v1/meta/config/country/USA")
        assert r.status_code == 200
        assert r.get_json()["country"] == "USA"

    def test_country_config_unknown_returns_404(self, client):
        r = client.get("/api/v1/meta/config/country/ZZZ")
        assert r.status_code == 404
        assert r.get_json()["error"]["code"] == "GEOGRAPHY_NOT_FOUND"

    def test_404_for_unknown_route(self, client):
        r = client.get("/api/v1/nonexistent")
        assert r.status_code == 404
        assert "error" in r.get_json()

    def test_meta_conditional_etag_returns_304(self, client):
        first = client.get("/api/v1/meta/indicators")
        assert first.status_code == 200
        etag = first.headers.get("ETag")
        assert etag
        assert "max-age=300" in first.headers.get("Cache-Control", "")

        second = client.get("/api/v1/meta/indicators", headers={"If-None-Match": etag})
        assert second.status_code == 304
