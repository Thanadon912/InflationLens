import pytest


class TestGlobalIndicatorEndpoints:
    @pytest.mark.parametrize(
        "indicator_id,body,expected_check",
        [
            (
                "median_country_inflation",
                {"country_rates": {"A": 1.0, "B": 2.0, "C": 3.0}, "all_geographies": ["A", "B", "C"], "period": "2026-06"},
                lambda d: d["value"] == 2.0,
            ),
            (
                "global_essential_inflation",
                {
                    "country_essential_rates": {"USA": 4.0, "EA": 3.0},
                    "consumption_ppp_weights": {"USA": 0.6, "EA": 0.4},
                    "all_geographies": ["USA", "EA"],
                    "period": "2026-06",
                },
                lambda d: d["value"] == pytest.approx(3.6),
            ),
            (
                "global_monetary_expansion",
                {
                    "country_money_growth_rates": {"USA": 6.0, "EA": 4.0},
                    "gdp_ppp_weights": {"USA": 0.5, "EA": 0.5},
                    "all_geographies": ["USA", "EA"],
                    "period": "2026-06",
                },
                lambda d: d["value"] == pytest.approx(5.0) and d["metadata"]["currency_conversion_applied"] is False,
            ),
            (
                "global_excess_money_growth",
                {
                    "all_geographies": ["USA", "EA"],
                    "period": "2026-Q2",
                    "global_money_expansion_percent": 7.0,
                    "global_real_gdp_growth_percent": 2.5,
                },
                lambda d: d["metadata"]["selected_method"] == "aggregate_first" and d["value"] == pytest.approx(4.5),
            ),
            (
                "global_producer_pressure",
                {
                    "country_ppi_rates": {"USA": 5.0, "EA": 3.0},
                    "gdp_ppp_weights": {"USA": 0.5, "EA": 0.5},
                    "country_import_rates": {"USA": 6.0, "EA": 4.0},
                    "import_share_weights": {"USA": 0.6, "EA": 0.4},
                    "commodity_rates": {"oil": 10.0, "metals": 2.0},
                    "commodity_weights": {"oil": 0.7, "metals": 0.3},
                    "all_geographies": ["USA", "EA"],
                    "period": "2026-06",
                },
                lambda d: d["value"] is None and next(c for c in d["components"] if c["key"] == "ppi_component")["value"] == pytest.approx(4.0),
            ),
            (
                "global_housing_asset_inflation",
                {
                    "country_house_price_current": {"USA": 110.0},
                    "country_house_price_prior": {"USA": 100.0},
                    "housing_weights": {"USA": 1.0},
                    "country_rent_rates": {"USA": 4.0},
                    "consumption_ppp_weights": {"USA": 1.0},
                    "all_geographies": ["USA"],
                    "period": "2026-Q2",
                    "asset_prices_current": {"gold": {"USD": 2200.0}},
                    "asset_prices_prior_year": {"gold": {"USD": 2000.0}},
                },
                lambda d: d["value"] is None and next(c for c in d["components"] if c["key"] == "gold_USD")["value"] == pytest.approx(10.0),
            ),
            (
                "global_inflation_synchronization",
                {"country_rates_current": {"A": 3.0, "B": 1.0}, "all_geographies": ["A", "B"], "period": "2026-06"},
                lambda d: d["metadata"]["threshold_percent"] == 2.0,
            ),
            (
                "global_inflation_synchronization",
                {"country_rates_current": {"A": 5.0, "B": 1.0}, "threshold_percent": 4.0, "all_geographies": ["A", "B"], "period": "2026-06"},
                lambda d: d["metadata"]["threshold_percent"] == 4.0,
            ),
        ],
    )
    def test_global_indicator_happy_paths(self, client, indicator_id, body, expected_check):
        r = client.post(f"/api/v1/global/{indicator_id}", json=body)
        assert r.status_code == 200
        assert expected_check(r.get_json())

    @pytest.mark.parametrize(
        "indicator_id,body,expected_status,expected_code",
        [
            (
                "global_consumer_inflation",
                {
                    "country_headline_rates": {"USA": 3.2, "EA": 2.5},
                    "country_weights": {"USA": 0.6, "EA": 0.4},
                    "all_geographies": ["USA", "EA", "THA"],
                    "period": "2026-06",
                },
                422,
                "COVERAGE_THRESHOLD",
            ),
            (
                "global_consumer_inflation",
                {
                    "country_headline_rates": {"USA": 3.2, "EA": 2.5},
                    "country_weights": {"USA": 0.6, "EA": 0.6},
                    "all_geographies": ["USA", "EA"],
                    "period": "2026-06",
                },
                422,
                "INVALID_WEIGHT",
            ),
            (
                "global_consumer_inflation",
                {"country_headline_rates": {"USA": 3.2}, "country_weights": {"USA": 1.0}, "period": "2026-06"},
                400,
                None,
            ),
            (
                "global_excess_money_growth",
                {
                    "method": "country_first",
                    "all_geographies": ["USA", "EA"],
                    "period": "2026-06",
                    "country_money_growth": {"USA": 7.0, "EA": 5.0},
                    "country_real_gdp_growth": {"USA": 2.0, "EA": 1.0},
                    "country_weights": {"USA": 0.5, "EA": 0.5},
                },
                400,
                None,
            ),
            ("not_a_real_indicator", {}, 404, None),
        ],
    )
    def test_global_validation_and_error_cases(self, client, indicator_id, body, expected_status, expected_code):
        r = client.post(f"/api/v1/global/{indicator_id}", json=body)
        assert r.status_code == expected_status
        if expected_code:
            assert r.get_json()["error"]["code"] == expected_code


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
