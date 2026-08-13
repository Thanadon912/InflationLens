class TestFixedLifestyleEndpoint:
    def test_happy_path(self, client):
        body = {
            "prices_current": {"rice": 12.0, "steak": 24.0},
            "prices_prior_year": {"rice": 11.0, "steak": 22.0},
            "prices_base": {"rice": 10.0, "steak": 20.0},
            "quantities_base": {"rice": 5.0, "steak": 2.0},
            "period": "2026-06",
        }
        r = client.post("/api/v1/country/USA/fixed_lifestyle_inflation", json=body)
        assert r.status_code == 200
        assert r.get_json()["value"] is not None

    def test_with_replacements(self, client):
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

    def test_missing_basket_item_returns_422(self, client):
        body = {
            "prices_current": {"rice": 12.0},
            "prices_prior_year": {"rice": 11.0, "steak": 22.0},
            "prices_base": {"rice": 10.0, "steak": 20.0},
            "quantities_base": {"rice": 5.0, "steak": 2.0},
            "period": "2026-06",
        }
        r = client.post("/api/v1/country/USA/fixed_lifestyle_inflation", json=body)
        assert r.status_code == 422


class TestBroadMoneyEndpoint:
    def test_happy_path_uses_country_profile_aggregate(self, client):
        body = {"money_current": 21500.0, "money_prior_year": 20000.0, "period": "2026-06"}
        r = client.post("/api/v1/country/USA/broad_money_expansion", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert data["metadata"]["aggregate_name"] == "M2"

    def test_ea_uses_m3(self, client):
        body = {"money_current": 21500.0, "money_prior_year": 20000.0, "period": "2026-06"}
        r = client.post("/api/v1/country/EA/broad_money_expansion", json=body)
        assert r.get_json()["metadata"]["aggregate_name"] == "M3"


class TestExcessMoneyEndpoint:
    def test_happy_path(self, client):
        body = {
            "money_growth_percent": 8.0,
            "real_output_growth_percent": 3.0,
            "money_period": "2026-Q2",
            "real_output_period": "2026-Q2",
            "period": "2026-Q2",
        }
        r = client.post("/api/v1/country/USA/excess_money_growth", json=body)
        assert r.status_code == 200
        assert r.get_json()["value"] == 5.0

    def test_mismatched_periods_returns_422(self, client):
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


class TestProducerImportEndpoint:
    def test_happy_path_uses_profile_weights(self, client):
        body = {
            "ppi_current": 110.0, "ppi_prior_year": 100.0,
            "import_price_current": 108.0, "import_price_prior_year": 100.0,
            "energy_inflation_percent": 10.0, "commodity_inflation_percent": 5.0,
            "period": "2026-06",
        }
        r = client.post("/api/v1/country/USA/producer_import_inflation", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert data["metadata"]["component_weights"]["ppi"] == 0.40


class TestPurchasingPowerEndpoint:
    def test_happy_path_uses_profile_wage_measure(self, client):
        body = {
            "nominal_wage_growth_percent": 5.0,
            "headline_inflation_percent": 3.0,
            "essential_inflation_percent": 4.0,
            "period": "2026-06",
        }
        r = client.post("/api/v1/country/USA/purchasing_power_squeeze", json=body)
        assert r.status_code == 200
        data = r.get_json()
        assert data["metadata"]["wage_measure"] == "mean"
        assert data["metadata"]["income_definition"] == "gross"
