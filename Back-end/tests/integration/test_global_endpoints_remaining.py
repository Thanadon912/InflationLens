import pytest


class TestGlobalEssentialEndpoint:
    def test_happy_path(self, client):
        body = {
            "country_essential_rates": {"USA": 4.0, "EA": 3.0},
            "consumption_ppp_weights": {"USA": 0.6, "EA": 0.4},
            "all_geographies": ["USA", "EA"],
            "period": "2026-06",
        }
        r = client.post("/api/v1/global/global_essential_inflation", json=body)
        assert r.status_code == 200
        assert r.get_json()["value"] == 3.6


class TestGlobalMonetaryEndpoint:
    def test_happy_path(self, client):
        body = {
            "country_money_growth_rates": {"USA": 6.0, "EA": 4.0},
            "gdp_ppp_weights": {"USA": 0.5, "EA": 0.5},
            "all_geographies": ["USA", "EA"],
            "period": "2026-06",
        }
        r = client.post("/api/v1/global/global_monetary_expansion", json=body)
        assert r.status_code == 200
        assert r.get_json()["value"] == 5.0
        assert r.get_json()["metadata"]["currency_conversion_applied"] is False


class TestGlobalExcessMoneyEndpoint:
    def test_uses_default_method_from_config(self, client):
        body = {
            "all_geographies": ["USA", "EA"],
            "period": "2026-06",
            "global_money_expansion_percent": 7.0,
            "global_real_gdp_growth_percent": 2.5,
        }
        r = client.post("/api/v1/global/global_excess_money_growth", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert data["metadata"]["selected_method"] == "aggregate_first"
        assert data["value"] == 4.5

    def test_explicit_method_override(self, client):
        body = {
            "method": "country_first",
            "all_geographies": ["USA", "EA"],
            "period": "2026-06",
            "country_money_growth": {"USA": 7.0, "EA": 5.0},
            "country_real_gdp_growth": {"USA": 2.0, "EA": 1.0},
            "country_weights": {"USA": 0.5, "EA": 0.5},
        }
        r = client.post("/api/v1/global/global_excess_money_growth", json=body)
        assert r.status_code == 200
        assert r.get_json()["metadata"]["selected_method"] == "country_first"


class TestGlobalProducerPressureEndpoint:
    def test_happy_path_uses_config_composite_weights(self, client):
        body = {
            "country_ppi_rates": {"USA": 5.0, "EA": 3.0},
            "gdp_ppp_weights": {"USA": 0.5, "EA": 0.5},
            "country_import_rates": {"USA": 6.0, "EA": 4.0},
            "import_share_weights": {"USA": 0.6, "EA": 0.4},
            "commodity_rates": {"oil": 10.0, "metals": 2.0},
            "commodity_weights": {"oil": 0.7, "metals": 0.3},
            "all_geographies": ["USA", "EA"],
            "period": "2026-06",
        }
        r = client.post("/api/v1/global/global_producer_pressure", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert data["value"] is None
        ppi = next(c for c in data["components"] if c["key"] == "ppi_component")
        assert ppi["value"] == 4.0


class TestGlobalHousingAssetsEndpoint:
    def test_happy_path(self, client):
        body = {
            "country_house_price_current": {"USA": 110.0, "EA": 105.0},
            "country_house_price_prior": {"USA": 100.0, "EA": 100.0},
            "housing_weights": {"USA": 0.6, "EA": 0.4},
            "country_rent_rates": {"USA": 4.0, "EA": 3.0},
            "consumption_ppp_weights": {"USA": 0.5, "EA": 0.5},
            "all_geographies": ["USA", "EA"],
            "period": "2026-Q2",
        }
        r = client.post("/api/v1/global/global_housing_asset_inflation", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert data["value"] is None
        assert any(c["key"] == "house_price" for c in data["components"])

    def test_with_multi_currency_assets(self, client):
        body = {
            "country_house_price_current": {"USA": 110.0},
            "country_house_price_prior": {"USA": 100.0},
            "housing_weights": {"USA": 1.0},
            "country_rent_rates": {"USA": 4.0},
            "consumption_ppp_weights": {"USA": 1.0},
            "all_geographies": ["USA"],
            "period": "2026-Q2",
            "asset_prices_current": {"gold": {"USD": 2200.0}},
            "asset_prices_prior_year": {"gold": {"USD": 2000.0}},
        }
        r = client.post("/api/v1/global/global_housing_asset_inflation", json=body)
        assert r.status_code == 200
        gold = next(c for c in r.get_json()["components"] if c["key"] == "gold_USD")
        assert gold["value"] == pytest.approx(10.0)


class TestGlobalSynchronizationEndpointOverride:
    def test_explicit_threshold_overrides_default(self, client):
        body = {
            "country_rates_current": {"A": 5.0, "B": 1.0},
            "threshold_percent": 4.0,
            "all_geographies": ["A", "B"],
            "period": "2026-06",
        }
        r = client.post("/api/v1/global/global_inflation_synchronization", json=body)
        assert r.status_code == 200
        assert r.get_json()["metadata"]["threshold_percent"] == 4.0
