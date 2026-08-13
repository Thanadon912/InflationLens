import pytest

from app import create_app


@pytest.fixture()
def client():
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
