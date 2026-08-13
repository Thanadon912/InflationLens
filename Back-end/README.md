# Multi-Dimensional Inflation Engine

Deterministic Python/Flask back end for ten country and eight global inflation lenses. It intentionally does not fetch data: provider adapters, persistence, caching and the React front end are separate phases.

## Install and verify

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q --cov=app --cov-report=term-missing --cov-fail-under=95
```

Run locally:

```bash
.venv/bin/flask --app app run --port 5000
```

A ready-to-run headline request is available at
`tests/fixtures/requests/usa_headline.json` for local smoke tests.

All routes are under `/api/v1`. Metadata is available at `/meta/indicators`, `/meta/methodology`, `/meta/global-weights`, and `/meta/countries`.

## Strict calculation contract

Version `0.2.0` accepts normalized observations only. Anonymous numeric fields are rejected. A country request has this shape:

```json
{
  "period": "2026-06",
  "inputs": {
    "money_current": [{
      "provider": "official-central-bank",
      "source_series_id": "M2",
      "indicator_id": "broad_money",
      "geography": "USA",
      "frequency": "monthly",
      "unit": "local_currency",
      "observation_period": "2026-06",
      "value": 22000.0,
      "retrieved_at": "2026-08-01T00:00:00Z",
      "validation_status": "validated",
      "source_url": "https://example.gov/series/M2",
      "data_vintage": "2026-08-01"
    }],
    "money_prior_year": [{
      "provider": "official-central-bank",
      "source_series_id": "M2",
      "indicator_id": "broad_money",
      "geography": "USA",
      "frequency": "monthly",
      "unit": "local_currency",
      "observation_period": "2025-06",
      "value": 20000.0,
      "retrieved_at": "2026-08-01T00:00:00Z",
      "validation_status": "validated"
    }]
  }
}
```

POST it to `/api/v1/country/USA/broad_money_expansion`. Mapping inputs contain one observation per country/category and identify the key with `component_id`. Global requests additionally require `universe` and lagged annual `population_by_geo`, `gdp_ppp_by_geo`, and `consumption_ppp_by_geo` roles. Global weights and coverage measures must use the previous annual period.

`GET /api/v1/meta/indicators` publishes each indicator's required roles, optional roles, accepted units/frequencies and allowed options. Formula/method/weight selection remains server-configured; requests cannot select a preferred result after seeing the data.

HTTP behavior: malformed contracts return 400, unknown geography/indicator 404, oversized bodies 413, and validly shaped but uncomputable data 422. Dashboard routes return individual unavailable results rather than failing the entire dashboard.

## Methodology rules

- Missing values are not filled or converted to zero.
- Rejected or pending observations never enter a calculation.
- Country basket coverage must be at least 80%. Global population coverage must be at least 80%; GDP-PPP and consumption-PPP coverage must be at least 85%.
- A missing component with at least 20% original weight is structurally dominant and cannot be silently renormalized.
- Scores use `standard_deviation_score`; they are not inflation rates.
- Weight arithmetic and chain-link multiplication use `Decimal`; public results remain JSON floats and are never rounded inside the engine.
- Every successful calculation emits a structured audit event containing provenance, periods, versions, warnings, output, software version and configured Git commit.

## Documented implementation choices

- Python's reserved `global` keyword requires the package name `global_`.
- Percentiles use linear/type-7 interpolation.
- Trimmed mean defaults to whole-component exclusion at a boundary; `clip` is the explicitly configured alternative.
- Fixed-Lifestyle quality-adjusted and raw price views are supplied separately; undocumented multiplicative quality factors are rejected.
- Model-based underlying inflation and the global common-factor model remain explicitly unavailable in v1.
- Public request-role declarations live in `app/api/contracts.py` and are exposed through the metadata endpoint; descriptive indicator names and outputs remain in YAML.

See [docs/FORMULA_TRACE.md](docs/FORMULA_TRACE.md) for formula/test traceability.
