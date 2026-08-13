from pathlib import Path

import pytest
import yaml

from app import create_app
from tests.integration.conftest import NormalizingClient, monthly_headline_observations


SNAPSHOTS = yaml.safe_load((Path(__file__).parents[1] / "snapshots" / "formula_outputs.yaml").read_text())


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as raw:
        yield NormalizingClient(raw)


def component(data, key):
    return next(item["value"] for item in data["components"] if item["key"] == key)


CASES = [
    ("headline_consumer_inflation", "/api/v1/country/USA/headline_consumer_inflation", lambda: {"observations": [dict(o, value=100.0) for o in monthly_headline_observations()[:-1]] + [dict(monthly_headline_observations()[-1], value=110.0)], "period": "2026-06"}, None),
    ("underlying_inflation", "/api/v1/country/USA/underlying_inflation", lambda: {"component_rates": {"a": 1.0, "b": 3.0, "c": 5.0}, "component_weights": {"a": 0.2, "b": 0.6, "c": 0.2}, "period": "2026-06"}, None),
    ("essential_cost_inflation", "/api/v1/country/USA/essential_cost_inflation", lambda: {"category_rates": {"food": 5.0, "housing": 5.0, "energy": 5.0, "transport": 5.0, "healthcare": 4.0, "communications": 4.0}, "period": "2026-06"}, None),
    ("fixed_lifestyle_inflation", "/api/v1/country/USA/fixed_lifestyle_inflation", lambda: {"prices_current": {"a": 11.0}, "prices_prior_year": {"a": 10.0}, "prices_base": {"a": 10.0}, "quantities_base": {"a": 1.0}, "period": "2026-06"}, None),
    ("housing_inflation", "/api/v1/country/USA/housing_inflation", lambda: {"rent_index_current": 110.0, "rent_index_prior_year": 100.0, "house_price_index_current": 105.0, "house_price_index_prior_year": 100.0, "period": "2026-06"}, "rent_inflation"),
    ("broad_money_expansion", "/api/v1/country/USA/broad_money_expansion", lambda: {"money_current": 110.0, "money_prior_year": 100.0, "period": "2026-06"}, None),
    ("excess_money_growth", "/api/v1/country/USA/excess_money_growth", lambda: {"money_growth_percent": 8.0, "real_output_growth_percent": 3.0, "money_period": "2026-Q2", "real_output_period": "2026-Q2", "period": "2026-Q2"}, None),
    ("producer_import_inflation", "/api/v1/country/USA/producer_import_inflation", lambda: {"ppi_current": 110.0, "ppi_prior_year": 100.0, "import_price_current": 110.0, "import_price_prior_year": 100.0, "energy_inflation_percent": 5.0, "commodity_inflation_percent": 5.0, "period": "2026-06"}, None),
    ("economy_wide_inflation", "/api/v1/country/USA/economy_wide_inflation", lambda: {"nominal_gdp_current": 110.0, "real_gdp_current": 100.0, "nominal_gdp_prior_year": 100.0, "real_gdp_prior_year": 100.0, "period": "2026-Q2"}, "gdp_deflator_inflation"),
    ("purchasing_power_squeeze", "/api/v1/country/USA/purchasing_power_squeeze", lambda: {"nominal_wage_growth_percent": 5.0, "headline_inflation_percent": 3.0, "essential_inflation_percent": 4.0, "period": "2026-06"}, None),
    ("global_consumer_inflation", "/api/v1/global/global_consumer_inflation", lambda: {"country_headline_rates": {"A": 4.0, "B": 3.0}, "country_weights": {"A": 0.6, "B": 0.4}, "all_geographies": ["A", "B"], "period": "2026-06"}, None),
    ("median_country_inflation", "/api/v1/global/median_country_inflation", lambda: {"country_rates": {"A": 1.0, "B": 2.0, "C": 3.0}, "all_geographies": ["A", "B", "C"], "period": "2026-06"}, None),
    ("global_essential_inflation", "/api/v1/global/global_essential_inflation", lambda: {"country_essential_rates": {"A": 4.0, "B": 3.0}, "consumption_ppp_weights": {"A": 0.6, "B": 0.4}, "all_geographies": ["A", "B"], "period": "2026-06"}, None),
    ("global_monetary_expansion", "/api/v1/global/global_monetary_expansion", lambda: {"country_money_growth_rates": {"A": 6.0, "B": 4.0}, "gdp_ppp_weights": {"A": 0.5, "B": 0.5}, "all_geographies": ["A", "B"], "period": "2026-06"}, None),
    ("global_excess_money_growth", "/api/v1/global/global_excess_money_growth", lambda: {"global_money_expansion_percent": 7.0, "global_real_gdp_growth_percent": 3.0, "all_geographies": ["A", "B"], "period": "2026-Q2"}, None),
    ("global_producer_pressure", "/api/v1/global/global_producer_pressure", lambda: {"country_ppi_rates": {"A": 5.0, "B": 3.0}, "gdp_ppp_weights": {"A": 0.5, "B": 0.5}, "country_import_rates": {"A": 4.0, "B": 2.0}, "import_share_weights": {"A": 0.5, "B": 0.5}, "commodity_rates": {"oil": 6.0}, "commodity_weights": {"oil": 1.0}, "all_geographies": ["A", "B"], "period": "2026-06"}, "ppi_component"),
    ("global_housing_asset_inflation", "/api/v1/global/global_housing_asset_inflation", lambda: {"country_house_price_current": {"A": 110.0, "B": 106.0}, "country_house_price_prior": {"A": 100.0, "B": 100.0}, "housing_weights": {"A": 0.5, "B": 0.5}, "country_rent_rates": {"A": 4.0, "B": 2.0}, "consumption_ppp_weights": {"A": 0.5, "B": 0.5}, "all_geographies": ["A", "B"], "period": "2026-Q2"}, "house_price"),
    ("global_inflation_synchronization", "/api/v1/global/global_inflation_synchronization", lambda: {"country_rates_current": {"A": 3.0, "B": 1.0}, "all_geographies": ["A", "B"], "period": "2026-06"}, None),
]


@pytest.mark.parametrize("indicator_id,path,payload_factory,component_key", CASES)
def test_formula_snapshot(client, indicator_id, path, payload_factory, component_key):
    response = client.post(path, json=payload_factory())
    assert response.status_code == 200, response.get_json()
    data = response.get_json()
    actual = component(data, component_key) if component_key else data["value"]
    assert actual == pytest.approx(SNAPSHOTS[indicator_id], abs=1e-9)
