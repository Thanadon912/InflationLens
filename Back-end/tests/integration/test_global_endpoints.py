class TestGlobalConsumerEndpoint:
    def test_happy_path(self, client):
        body = {
            "country_headline_rates": {"USA": 3.2, "EA": 2.5},
            "country_weights": {"USA": 0.6, "EA": 0.4},
            "all_geographies": ["USA", "EA", "THA"],
            "period": "2026-06",
        }
        r = client.post("/api/v1/global/global_consumer_inflation", json=body)
        assert r.status_code == 422
        assert r.get_json()["error"]["code"] == "COVERAGE_THRESHOLD"

    def test_invalid_weights_returns_422(self, client):
        body = {
            "country_headline_rates": {"USA": 3.2, "EA": 2.5},
            "country_weights": {"USA": 0.6, "EA": 0.6},  # sums to 1.2
            "all_geographies": ["USA", "EA"],
            "period": "2026-06",
        }
        r = client.post("/api/v1/global/global_consumer_inflation", json=body)
        assert r.status_code == 422
        assert r.get_json()["error"]["code"] == "INVALID_WEIGHT"

    def test_missing_all_geographies_returns_400(self, client):
        body = {"country_headline_rates": {"USA": 3.2}, "country_weights": {"USA": 1.0}, "period": "2026-06"}
        r = client.post("/api/v1/global/global_consumer_inflation", json=body)
        assert r.status_code == 400


class TestMedianCountryEndpoint:
    def test_happy_path(self, client):
        body = {
            "country_rates": {"A": 1.0, "B": 2.0, "C": 3.0},
            "all_geographies": ["A", "B", "C"],
            "period": "2026-06",
        }
        r = client.post("/api/v1/global/median_country_inflation", json=body)
        assert r.status_code == 200
        assert r.get_json()["value"] == 2.0


class TestSynchronizationEndpoint:
    def test_uses_default_threshold_from_config(self, client):
        body = {
            "country_rates_current": {"A": 3.0, "B": 1.0},
            "all_geographies": ["A", "B"],
            "period": "2026-06",
        }
        r = client.post("/api/v1/global/global_inflation_synchronization", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert data["metadata"]["threshold_percent"] == 2.0  # from global_weights.yaml default


class TestGlobalUnknownIndicator:
    def test_returns_404(self, client):
        r = client.post("/api/v1/global/not_a_real_indicator", json={})
        assert r.status_code == 404


class TestGlobalDashboard:
    def test_partial_dashboard(self, client):
        body = {
            "median_country_inflation": {
                "country_rates": {"A": 1.0, "B": 2.0},
                "all_geographies": ["A", "B"],
                "period": "2026-06",
            }
        }
        r = client.post("/api/v1/global/dashboard", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert len(data["indicators"]) == 8
        by_id = {i["indicator_id"]: i for i in data["indicators"]}
        assert by_id["median_country_inflation"]["coverage"] == "full"
        assert by_id["global_monetary_expansion"]["coverage"] == "unavailable"
