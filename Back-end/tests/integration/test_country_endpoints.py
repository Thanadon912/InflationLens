import pytest

from tests.integration.conftest import monthly_headline_observations


class TestHeadlineConsumerEndpoint:
    def test_happy_path_returns_full_result_contract_and_provenance(self, client):
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
        assert data["input_series"][0]["provider"] == "bls"
        assert data["input_series"][0]["series_id"] == "CUUR0000SA0"

    def test_unit_mismatch_returns_422_not_zero(self, client):
        obs = monthly_headline_observations()
        for o in obs:
            o["unit"] = "percent_yoy"
        r = client.post("/api/v1/country/USA/headline_consumer_inflation", json={"observations": obs, "period": "2026-06"})
        assert r.status_code == 422
        assert r.get_json()["error"]["code"] == "UNIT_MISMATCH"

    @pytest.mark.parametrize(
        "path,payload,content_type,expected_status,expected_code",
        [
            ("/api/v1/country/EA/headline_consumer_inflation", {"observations": monthly_headline_observations(), "period": "2026-06"}, "application/json", 400, None),
            ("/api/v1/country/USA/headline_consumer_inflation", {"period": "2026-06"}, "application/json", 400, "SCHEMA_ERROR"),
            ("/api/v1/country/USA/headline_consumer_inflation", "not json", "application/json", 400, None),
            ("/api/v1/country/USA/not_a_real_indicator", {}, "application/json", 404, "INDICATOR_NOT_FOUND"),
        ],
    )
    def test_error_responses(self, client, path, payload, content_type, expected_status, expected_code):
        kwargs = {"json": payload} if isinstance(payload, dict) else {"data": payload, "content_type": content_type}
        r = client.post(path, **kwargs)
        assert r.status_code == expected_status
        if expected_code:
            assert r.get_json()["error"]["code"] == expected_code


class TestCountryIndicatorEndpoints:
    @pytest.mark.parametrize(
        "geo,indicator_id,body,expected_check",
        [
            (
                "USA",
                "underlying_inflation",
                {
                    "component_rates": {"food": 6.0, "energy": 12.0, "shelter": 4.0, "core_goods": 2.0},
                    "component_weights": {"food": 0.2, "energy": 0.1, "shelter": 0.5, "core_goods": 0.2},
                    "period": "2026-06",
                },
                lambda d: d["metadata"]["selected_method"] == "weighted_median",
            ),
            (
                "USA",
                "essential_cost_inflation",
                {
                    "category_rates": {"food": 5.0, "housing": 6.0, "energy": 10.0, "transport": 3.0, "healthcare": 2.0, "communications": 1.0},
                    "period": "2026-06",
                },
                lambda d: d["value"] > 0,
            ),
            (
                "USA",
                "fixed_lifestyle_inflation",
                {
                    "prices_current": {"rice": 12.0, "steak": 24.0},
                    "prices_prior_year": {"rice": 11.0, "steak": 22.0},
                    "prices_base": {"rice": 10.0, "steak": 20.0},
                    "quantities_base": {"rice": 5.0, "steak": 2.0},
                    "period": "2026-06",
                },
                lambda d: d["value"] is not None,
            ),
            (
                "USA",
                "housing_inflation",
                {
                    "rent_index_current": 104.0, "rent_index_prior_year": 100.0,
                    "house_price_index_current": 106.0, "house_price_index_prior_year": 100.0,
                    "property_price_current": 420000.0, "property_price_prior_year": 400000.0,
                    "mortgage_rate_current": 0.065, "mortgage_rate_prior_year": 0.06,
                    "period": "2026-06",
                },
                lambda d: d["value"] is None and any(c["key"] == "mortgage_payment_inflation" for c in d["components"]),
            ),
            (
                "USA",
                "broad_money_expansion",
                {"money_current": 21500.0, "money_prior_year": 20000.0, "period": "2026-06"},
                lambda d: d["metadata"]["aggregate_name"] == "M2",
            ),
            (
                "EA",
                "broad_money_expansion",
                {"money_current": 21500.0, "money_prior_year": 20000.0, "period": "2026-06"},
                lambda d: d["metadata"]["aggregate_name"] == "M3",
            ),
            (
                "USA",
                "excess_money_growth",
                {
                    "money_growth_percent": 8.0,
                    "real_output_growth_percent": 3.0,
                    "money_period": "2026-Q2",
                    "real_output_period": "2026-Q2",
                    "period": "2026-Q2",
                },
                lambda d: d["value"] == 5.0,
            ),
            (
                "USA",
                "producer_import_inflation",
                {
                    "ppi_current": 110.0, "ppi_prior_year": 100.0,
                    "import_price_current": 108.0, "import_price_prior_year": 100.0,
                    "energy_inflation_percent": 10.0, "commodity_inflation_percent": 5.0,
                    "period": "2026-06",
                },
                lambda d: d["metadata"]["component_weights"]["ppi"] == 0.40,
            ),
            (
                "USA",
                "economy_wide_inflation",
                {
                    "nominal_gdp_current": 26000.0, "real_gdp_current": 25000.0,
                    "nominal_gdp_prior_year": 24500.0, "real_gdp_prior_year": 24000.0,
                    "period": "2026-Q2",
                },
                lambda d: d["value"] is None,
            ),
            (
                "USA",
                "purchasing_power_squeeze",
                {
                    "nominal_wage_growth_percent": 5.0,
                    "headline_inflation_percent": 3.0,
                    "essential_inflation_percent": 4.0,
                    "period": "2026-06",
                },
                lambda d: d["metadata"]["wage_measure"] == "mean" and d["metadata"]["income_definition"] == "gross",
            ),
        ],
    )
    def test_country_indicator_happy_paths(self, client, geo, indicator_id, body, expected_check):
        r = client.post(f"/api/v1/country/{geo}/{indicator_id}", json=body)
        assert r.status_code == 200
        assert expected_check(r.get_json())

    def test_fixed_lifestyle_with_replacements_and_missing_item(self, client):
        body = {
            "prices_current": {"rice": 12.0, "steak": 24.0},
            "prices_prior_year": {"rice": 11.0, "steak": 22.0},
            "prices_base": {"rice": 10.0, "steak": 20.0},
            "quantities_base": {"rice": 5.0, "steak": 2.0},
            "period": "2026-06",
            "replacements": {"steak": {"replacement_level": "category_proxy", "note": "beef shortage"}},
        }
        r = client.post("/api/v1/country/USA/fixed_lifestyle_inflation", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert data["coverage"] == "partial"
        assert data["metadata"]["replacements"]["steak"] == "category_proxy"

        bad_body = {**body, "prices_current": {"rice": 12.0}}
        bad_body.pop("replacements")
        assert client.post("/api/v1/country/USA/fixed_lifestyle_inflation", json=bad_body).status_code == 422

    def test_excess_money_mismatched_periods_returns_422(self, client):
        body = {
            "money_growth_percent": 8.0,
            "real_output_growth_percent": 3.0,
            "money_period": "2026-06",
            "money_frequency": "monthly",
            "real_output_period": "2026-Q1",
            "real_output_frequency": "quarterly",
            "period": "2026-06",
        }
        r = client.post("/api/v1/country/USA/excess_money_growth", json=body)
        assert r.status_code == 422
        assert r.get_json()["error"]["code"] == "PERIOD_ALIGNMENT"


class TestDashboardEndpoint:
    def test_partial_and_failed_indicators_become_unavailable_not_500(self, client):
        body = {
            "essential_cost_inflation": {
                "category_rates": {"food": 5.0, "housing": 6.0, "energy": 10.0, "transport": 3.0, "healthcare": 2.0, "communications": 1.0},
                "period": "2026-06",
            }
        }
        r = client.post("/api/v1/country/USA/dashboard", json=body)
        assert r.status_code == 200
        by_id = {i["indicator_id"]: i for i in r.get_json()["indicators"]}
        assert len(by_id) == 10
        assert by_id["essential_cost_inflation"]["coverage"] == "full"
        assert by_id["broad_money_expansion"]["coverage"] == "unavailable"
        assert by_id["broad_money_expansion"]["value"] is None

        failed = client.post(
            "/api/v1/country/USA/dashboard",
            json={"essential_cost_inflation": {"category_rates": {"nonexistent_category": 5.0}, "period": "2026-06"}},
        )
        assert failed.status_code == 200
        failed_by_id = {i["indicator_id"]: i for i in failed.get_json()["indicators"]}
        assert failed_by_id["essential_cost_inflation"]["coverage"] == "unavailable"
        assert "calculation failed" in failed_by_id["essential_cost_inflation"]["warnings"][0]
