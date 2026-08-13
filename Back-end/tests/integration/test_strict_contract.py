import pytest


def obs(role, value, period="2026-06", *, geography="USA", unit="percent_yoy", frequency="monthly", component_id=None, status="validated"):
    return {
        "provider": "official-test",
        "source_series_id": f"SERIES:{role}:{component_id or geography}",
        "indicator_id": role,
        "geography": geography,
        "frequency": frequency,
        "unit": unit,
        "observation_period": period,
        "value": value,
        "retrieved_at": "2026-08-01T00:00:00Z",
        "validation_status": status,
        "source_url": "https://example.test/official",
        "data_vintage": "2026-08-01",
        **({"component_id": component_id} if component_id else {}),
    }


def coverage_inputs(geographies):
    return {
        role: [obs(role, 1.0, "2025", geography=g, unit="persons" if role == "population_by_geo" else "currency", frequency="annual", component_id=g) for g in geographies]
        for role in ("population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo")
    }


class TestStrictCountryContract:
    def test_raw_numeric_payload_is_rejected(self, raw_client):
        response = raw_client.post("/api/v1/country/USA/broad_money_expansion", json={"period": "2026-06", "money_current": 110, "money_prior_year": 100})
        assert response.status_code == 400

    def test_rejected_observation_is_domain_error(self, raw_client):
        payload = {
            "period": "2026-06",
            "inputs": {
                "money_current": [obs("broad_money", 110, unit="local_currency", status="rejected")],
                "money_prior_year": [obs("broad_money", 100, "2025-06", unit="local_currency")],
            },
        }
        response = raw_client.post("/api/v1/country/USA/broad_money_expansion", json=payload)
        assert response.status_code == 422
        assert response.get_json()["error"]["code"] == "DATA_QUALITY"

    def test_valid_result_preserves_full_provenance_and_versions(self, raw_client):
        payload = {
            "period": "2026-06",
            "inputs": {
                "money_current": [obs("broad_money", 110, unit="local_currency")],
                "money_prior_year": [obs("broad_money", 100, "2025-06", unit="local_currency")],
            },
        }
        response = raw_client.post("/api/v1/country/USA/broad_money_expansion", json=payload)
        assert response.status_code == 200
        data = response.get_json()
        assert data["value"] == pytest.approx(10.0)
        assert data["methodology_version"] == "1.0.1"
        assert data["config_version"] == "1.1.0"
        assert data["input_series"][0]["source_url"] == "https://example.test/official"
        assert data["input_series"][0]["data_vintage"] == "2026-08-01"

    def test_zero_population_is_422_not_500(self, raw_client):
        payload = {
            "period": "2026-06",
            "inputs": {
                "money_current": [obs("broad_money", 110, unit="local_currency")],
                "money_prior_year": [obs("broad_money", 100, "2025-06", unit="local_currency")],
                "population_current": [obs("population", 0, unit="persons")],
                "population_prior_year": [obs("population", 10, "2025-06", unit="persons")],
            },
        }
        response = raw_client.post("/api/v1/country/USA/broad_money_expansion", json=payload)
        assert response.status_code == 422

    def test_wrong_scalar_unit_is_rejected(self, raw_client):
        payload = {
            "period": "2026-06",
            "inputs": {
                "money_current": [obs("broad_money", 110, unit="persons")],
                "money_prior_year": [obs("broad_money", 100, "2025-06", unit="local_currency")],
            },
        }
        response = raw_client.post("/api/v1/country/USA/broad_money_expansion", json=payload)
        assert response.status_code == 422
        assert response.get_json()["error"]["code"] == "UNIT_MISMATCH"

    def test_duplicate_mapping_key_is_rejected(self, raw_client):
        duplicate = obs("component", 2.0, component_id="food")
        payload = {
            "period": "2026-06",
            "inputs": {
                "component_rates": [duplicate, {**duplicate, "value": 3.0}],
                "component_weights": [obs("weight", 1.0, "2025", unit="ratio", frequency="annual", component_id="food")],
            },
        }
        response = raw_client.post("/api/v1/country/USA/underlying_inflation", json=payload)
        assert response.status_code == 400

    def test_payload_larger_than_two_megabytes_is_rejected(self, raw_client):
        response = raw_client.post(
            "/api/v1/country/USA/broad_money_expansion",
            data=b"x" * (2 * 1024 * 1024 + 1),
            content_type="application/json",
        )
        assert response.status_code == 413


class TestStrictGlobalContract:
    def payload(self, universe=("A", "B")):
        inputs = {
            "country_headline_rates": [obs("headline_consumer_inflation", 3.0 + i, geography=g, component_id=g) for i, g in enumerate(universe)],
            "country_weights": [obs("consumption_ppp_weight", 1 / len(universe), "2025", geography=g, unit="ratio", frequency="annual", component_id=g) for g in universe],
            **coverage_inputs(universe),
        }
        return {"period": "2026-06", "universe": list(universe), "inputs": inputs}

    def test_valid_global_request_has_complete_coverage(self, raw_client):
        response = raw_client.post("/api/v1/global/global_consumer_inflation", json=self.payload())
        assert response.status_code == 200
        report = response.get_json()["coverage_report"]
        assert report["population_coverage_percent"] == 100.0
        assert report["gdp_ppp_coverage_percent"] == 100.0
        assert report["consumption_ppp_coverage_percent"] == 100.0

    def test_geometric_relative_can_be_chain_linked_and_compared_yoy(self, raw_client):
        payload = self.payload()
        payload["inputs"].update({
            "country_price_relatives": [
                obs("country_price_relative", 1.02, geography="A", unit="ratio", component_id="A"),
                obs("country_price_relative", 1.04, geography="B", unit="ratio", component_id="B"),
            ],
            "global_index_previous_period": [obs("global_index", 110.0, "2026-05", unit="index")],
            "global_index_prior_year": [obs("global_index", 100.0, "2025-06", unit="index")],
        })
        response = raw_client.post("/api/v1/global/global_consumer_inflation", json=payload)
        assert response.status_code == 200
        components = {item["key"]: item["value"] for item in response.get_json()["components"]}
        assert components["geometric_period_relative_percent"] == pytest.approx((1.02 ** 0.5 * 1.04 ** 0.5 - 1) * 100)
        assert components["geometric_global_index"] == pytest.approx(110 * 1.02 ** 0.5 * 1.04 ** 0.5)
        assert components["geometric_yoy"] == pytest.approx(components["geometric_global_index"] - 100)

    def test_current_period_weights_are_rejected(self, raw_client):
        payload = self.payload()
        for item in payload["inputs"]["country_weights"]:
            item["observation_period"] = "2026"
        response = raw_client.post("/api/v1/global/global_consumer_inflation", json=payload)
        assert response.status_code == 422
        assert response.get_json()["error"]["code"] == "PERIOD_ALIGNMENT"

    def test_partial_weights_are_renormalized_and_disclosed(self, raw_client):
        payload = self.payload(("A", "B", "C"))
        payload["inputs"]["country_headline_rates"] = payload["inputs"]["country_headline_rates"][:2]
        # C is small enough not to be structurally dominant and coverage
        # measures retain 90%, above all configured thresholds.
        payload["inputs"]["country_weights"][0]["value"] = 0.45
        payload["inputs"]["country_weights"][1]["value"] = 0.45
        payload["inputs"]["country_weights"][2]["value"] = 0.10
        for role in ("population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"):
            payload["inputs"][role][0]["value"] = 0.45
            payload["inputs"][role][1]["value"] = 0.45
            payload["inputs"][role][2]["value"] = 0.10
        response = raw_client.post("/api/v1/global/global_consumer_inflation", json=payload)
        assert response.status_code == 200
        report = response.get_json()["coverage_report"]
        assert report["weights_renormalized"] is True
        assert sum(report["adjusted_weights"].values()) == pytest.approx(1.0)
        assert report["original_weights"]["C"] == 0.10

    def test_audit_event_contains_versions_without_raw_payload(self, raw_client, caplog):
        with caplog.at_level("INFO", logger="inflation_engine.audit"):
            response = raw_client.post("/api/v1/global/global_consumer_inflation", json=self.payload())
        assert response.status_code == 200
        event = next(record.message for record in caplog.records if '"event": "indicator_calculated"' in record.message)
        assert '"methodology_version": "1.0.1"' in event
        assert '"config_version": "global-weights-1.1.0"' in event
        assert '"inputs"' not in event

    def test_empty_synchronization_is_schema_error_not_500(self, raw_client):
        payload = {"period": "2026-06", "universe": ["A"], "inputs": {"country_rates_current": [], **coverage_inputs(("A",))}}
        response = raw_client.post("/api/v1/global/global_inflation_synchronization", json=payload)
        assert response.status_code == 400
