import pytest

from app import create_app
from app.api.contracts import EXPECTED_INDICATOR_IDS, MAPPING_ROLES, RATE_ROLES, WEIGHT_ROLES


def _shift_year(period: str) -> str:
    return f"{int(period[:4]) - 1}{period[4:]}"


def _observation(role, value, period, geography, *, component_id=None):
    if role in WEIGHT_ROLES or "quantit" in role or "factor" in role or "price_relative" in role or role.startswith("mortgage_rate_"):
        unit = "ratio"
    elif role in RATE_ROLES or "growth" in role or "inflation_percent" in role:
        unit = "percent_yoy"
    elif "population" in role:
        unit = "persons"
    elif "index" in role or "ppi_" in role:
        unit = "index"
    else:
        unit = "currency"
    frequency = "quarterly" if "Q" in period else "annual" if len(period) == 4 else "monthly"
    return {
        "provider": "test-official",
        "source_series_id": f"{role}:{component_id or geography}",
        "indicator_id": EXPECTED_INDICATOR_IDS.get(role, role),
        "geography": geography,
        "frequency": frequency,
        "unit": unit,
        "observation_period": period,
        "value": value,
        "retrieved_at": "2026-08-02T12:00:00Z",
        "validation_status": "validated",
        **({"component_id": component_id} if component_id else {}),
    }


def strictify(path, body):
    """Translate old integration fixtures at the test boundary.

    Production accepts only the resulting normalized contract. Dedicated
    strict-contract tests use ``raw_client`` and bypass this compatibility
    fixture entirely.
    """
    if not isinstance(body, dict) or "/api/v1/" not in path or path.endswith("/dashboard"):
        if path.endswith("/dashboard") and isinstance(body, dict):
            return {key: strictify(path.rsplit("/", 1)[0] + "/" + key, value) for key, value in body.items()}
        return body
    parts = path.strip("/").split("/")
    if len(parts) < 4 or parts[2] not in {"country", "global"}:
        return body
    global_scope = parts[2] == "global"
    indicator_id = parts[-1]
    period = body.get("period", "2026-06")
    geography = "GLOBAL" if global_scope else parts[3].upper()
    inputs = {}
    options = {}
    ignored = {"period", "all_geographies", "money_period", "real_output_period", "money_frequency", "real_output_frequency", "method", "money_weight_basis", "gdp_weight_basis", "weight_method"}
    option_names = {"replacements", "standardization_windows", "upp_standardization_window", "threshold_percent", "dispersion_standardization_window", "asset_prices_current", "asset_prices_prior_year"}
    if indicator_id == "headline_consumer_inflation" and "observations" in body:
        inputs["all_items_cpi_index"] = body["observations"]
    for role, value in body.items():
        if role in ignored or role == "observations":
            continue
        if role in option_names:
            options[role] = value
            continue
        if role == "money_growth_percent" and body.get("money_period"):
            role_period = body["money_period"]
        elif role == "real_output_growth_percent" and body.get("real_output_period"):
            role_period = body["real_output_period"]
        else:
            role_period = str(int(period[:4]) - 1) if role in WEIGHT_ROLES else _shift_year(period) if role.endswith(("_prior", "_prior_year")) else period
        if isinstance(value, dict):
            inputs[role] = [_observation(role, v, role_period, str(k) if global_scope else geography, component_id=str(k)) for k, v in value.items()]
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            item = _observation(role, value, role_period, geography)
            if role == "money_growth_percent" and body.get("money_frequency"):
                item["frequency"] = body["money_frequency"]
            if role == "real_output_growth_percent" and body.get("real_output_frequency"):
                item["frequency"] = body["real_output_frequency"]
            inputs[role] = [item]
    universe = body.get("all_geographies", [])
    if global_scope:
        for coverage_role in ("population_by_geo", "gdp_ppp_by_geo", "consumption_ppp_by_geo"):
            if coverage_role not in inputs:
                inputs[coverage_role] = [_observation(coverage_role, 1.0, str(int(period[:4]) - 1), geo, component_id=geo) for geo in universe]
    result = {"period": period, "inputs": inputs}
    if options:
        result["options"] = options
    if global_scope:
        result["universe"] = universe
    return result


class NormalizingClient:
    def __init__(self, client):
        self._client = client

    def post(self, path, *args, **kwargs):
        if "json" in kwargs:
            kwargs["json"] = strictify(path, kwargs["json"])
        return self._client.post(path, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._client, name)


@pytest.fixture()
def client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield NormalizingClient(c)


@pytest.fixture()
def raw_client():
    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c


def monthly_headline_observations(months: int = 16, start_year: int = 2025, start_month: int = 3, base: float = 300.0, growth: float = 0.003):
    obs = []
    value = base
    for i in range(months):
        total = (start_month - 1) + i
        y = start_year + total // 12
        m = total % 12 + 1
        obs.append(
            {
                "provider": "bls",
                "source_series_id": "CUUR0000SA0",
                "indicator_id": "headline_consumer_inflation",
                "geography": "USA",
                "frequency": "monthly",
                "unit": "index",
                "observation_period": f"{y:04d}-{m:02d}",
                "value": round(value, 6),
                "retrieved_at": "2026-08-02T12:00:00Z",
                "validation_status": "validated",
            }
        )
        value *= 1 + growth
    return obs
