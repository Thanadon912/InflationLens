from tests.integration.conftest import monthly_headline_observations


class TestHeadlineConsumerEndpoint:
    def test_happy_path_returns_full_result_contract(self, client):
        body = {"observations": monthly_headline_observations(), "period": "2026-06"}
        r = client.post("/api/v1/country/USA/headline_consumer_inflation", json=body)
        assert r.status_code == 200
        data = r.get_json()
        for field in [
            "indicator_id", "geography", "period", "value", "unit", "method",
            "methodology_version", "input_series", "coverage", "confidence",
            "is_estimated", "warnings", "calculated_at",
        ]:
            assert field in data
        assert data["value"] > 0

    def test_provenance_survives_from_input_to_result(self, client):
        body = {"observations": monthly_headline_observations(), "period": "2026-06"}
        r = client.post("/api/v1/country/USA/headline_consumer_inflation", json=body)
        data = r.get_json()
        assert data["input_series"][0]["provider"] == "bls"
        assert data["input_series"][0]["series_id"] == "CUUR0000SA0"

    def test_unit_mismatch_returns_422_not_zero(self, client):
        obs = monthly_headline_observations()
        for o in obs:
            o["unit"] = "percent_yoy"
        body = {"observations": obs, "period": "2026-06"}
        r = client.post("/api/v1/country/USA/headline_consumer_inflation", json=body)
        assert r.status_code == 422
        assert r.get_json()["error"]["code"] == "UNIT_MISMATCH"

    def test_geography_mismatch_returns_400(self, client):
        obs = monthly_headline_observations()
        body = {"observations": obs, "period": "2026-06"}
        r = client.post("/api/v1/country/EA/headline_consumer_inflation", json=body)
        assert r.status_code == 400

    def test_missing_observations_field_returns_400(self, client):
        r = client.post("/api/v1/country/USA/headline_consumer_inflation", json={"period": "2026-06"})
        assert r.status_code == 400
        assert r.get_json()["error"]["code"] == "SCHEMA_ERROR"

    def test_malformed_json_returns_400(self, client):
        r = client.post(
            "/api/v1/country/USA/headline_consumer_inflation",
            data="not json", content_type="application/json",
        )
        assert r.status_code == 400

    def test_unknown_indicator_returns_404(self, client):
        r = client.post("/api/v1/country/USA/not_a_real_indicator", json={})
        assert r.status_code == 404
        assert r.get_json()["error"]["code"] == "INDICATOR_NOT_FOUND"


class TestUnderlyingEndpoint:
    def test_happy_path(self, client):
        body = {
            "component_rates": {"food": 6.0, "energy": 12.0, "shelter": 4.0, "core_goods": 2.0},
            "component_weights": {"food": 0.2, "energy": 0.1, "shelter": 0.5, "core_goods": 0.2},
            "period": "2026-06",
        }
        r = client.post("/api/v1/country/USA/underlying_inflation", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert data["metadata"]["selected_method"] == "weighted_median"


class TestEssentialCostEndpoint:
    def test_happy_path(self, client):
        body = {
            "category_rates": {"food": 5.0, "housing": 6.0, "energy": 10.0, "transport": 3.0, "healthcare": 2.0, "communications": 1.0},
            "period": "2026-06",
        }
        r = client.post("/api/v1/country/USA/essential_cost_inflation", json=body)
        assert r.status_code == 200
        assert r.get_json()["value"] > 0


class TestHousingEndpoint:
    def test_happy_path_with_full_mortgage_data(self, client):
        body = {
            "rent_index_current": 104.0, "rent_index_prior_year": 100.0,
            "house_price_index_current": 106.0, "house_price_index_prior_year": 100.0,
            "property_price_current": 420000.0, "property_price_prior_year": 400000.0,
            "mortgage_rate_current": 0.065, "mortgage_rate_prior_year": 0.06,
            "period": "2026-06",
        }
        r = client.post("/api/v1/country/USA/housing_inflation", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert data["value"] is None  # never averaged into one number
        assert any(c["key"] == "mortgage_payment_inflation" for c in data["components"])

    def test_minimal_data_marks_partial(self, client):
        body = {
            "rent_index_current": 104.0, "rent_index_prior_year": 100.0,
            "house_price_index_current": 106.0, "house_price_index_prior_year": 100.0,
            "period": "2026-06",
        }
        r = client.post("/api/v1/country/USA/housing_inflation", json=body)
        assert r.status_code == 200
        assert r.get_json()["coverage"] == "partial"


class TestEconomyWideEndpoint:
    def test_never_averages_deflators(self, client):
        body = {
            "nominal_gdp_current": 26000.0, "real_gdp_current": 25000.0,
            "nominal_gdp_prior_year": 24500.0, "real_gdp_prior_year": 24000.0,
            "period": "2026-Q2",
        }
        r = client.post("/api/v1/country/USA/economy_wide_inflation", json=body)
        assert r.status_code == 200
        assert r.get_json()["value"] is None


class TestDashboardEndpoint:
    def test_partial_dashboard_marks_unrequested_as_unavailable(self, client):
        body = {
            "essential_cost_inflation": {
                "category_rates": {"food": 5.0, "housing": 6.0, "energy": 10.0, "transport": 3.0, "healthcare": 2.0, "communications": 1.0},
                "period": "2026-06",
            }
        }
        r = client.post("/api/v1/country/USA/dashboard", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert len(data["indicators"]) == 10
        by_id = {i["indicator_id"]: i for i in data["indicators"]}
        assert by_id["essential_cost_inflation"]["coverage"] == "full"
        assert by_id["broad_money_expansion"]["coverage"] == "unavailable"
        assert by_id["broad_money_expansion"]["value"] is None

    def test_failed_indicator_becomes_unavailable_not_500(self, client):
        # essential_cost with a category not in the config basket at all
        body = {"essential_cost_inflation": {"category_rates": {"nonexistent_category": 5.0}, "period": "2026-06"}}
        r = client.post("/api/v1/country/USA/dashboard", json=body)
        assert r.status_code == 200
        by_id = {i["indicator_id"]: i for i in r.get_json()["indicators"]}
        assert by_id["essential_cost_inflation"]["coverage"] == "unavailable"
        assert "calculation failed" in by_id["essential_cost_inflation"]["warnings"][0]

    def test_empty_body_marks_everything_unavailable(self, client):
        r = client.post("/api/v1/country/USA/dashboard", json={})
        data = r.get_json()
        assert all(i["coverage"] == "unavailable" for i in data["indicators"])
        assert all(i["value"] is None for i in data["indicators"])
