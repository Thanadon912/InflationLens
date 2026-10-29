# Multi-Dimensional Inflation Engine

Deterministic Python/Flask back end for ten country and eight global inflation lenses. The calculation API accepts normalized observations for every implemented lens. A production-oriented ingestion layer also fetches four core lenses for the United States and euro area from official providers, preserves their lineage in SQLite, and serves calculated snapshots without making provider calls during web requests.

## Install and verify

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest -q --cov=app --cov-branch --cov-report=term-missing
```

The 97% coverage gate (`[tool.coverage.report] fail_under` in `pyproject.toml`)
applies automatically whenever `--cov` is passed -- no `--cov-fail-under` flag
needed. A bare `pytest` (no `--cov`) skips coverage entirely, so running a
single test file during development never fails on unrelated coverage. `live`
tests (real, read-only calls to official provider APIs) are excluded by
default (`addopts = -m "not live"`); run them explicitly with `-m live`.

Run locally:

```bash
.venv/bin/flask --app app run --port 5000
```

A ready-to-run headline request is available at
`tests/fixtures/requests/usa_headline.json` for local smoke tests.

All routes are under `/api/v1`. Metadata is available at `/meta/indicators`, `/meta/methodology`, `/meta/global-weights`, and `/meta/countries`.

### Load testing

`pytest` proves the engine is correct; it never measures how long anything
takes. That lives in [`../perf/`](../perf/README.md) -- a k6 suite that drives
the API under concurrency and reports against explicit SLOs.

```bash
.venv/bin/pip install -e '.[perf]'   # adds gunicorn
cd .. && ./perf/scripts/run.sh load
```

Two things there matter to backend work. It runs the API on **gunicorn**, not
`flask run`, because the development server serves requests one at a time and
measuring it under load measures the dev server. And it seeds its own cache with
`scripts/seed_perf_db.py` -- the same public store API as `seed_e2e_db.py`, but
at the volume `flask data sync` really produces (7 measures x 24 months, ~220
economies in the cross-section), so payload sizes are the real ones.

## Official data ingestion

Copy `.env.example` to `.env`, then set `FRED_API_KEY` and `BEA_API_KEY`. BLS, Eurostat, ECB, and World Bank do not require a key for the configured endpoints. Provider access is CLI-only: Flask GET routes read cached SQLite snapshots and therefore remain deterministic even when a provider is slow or unavailable.

```bash
# Fetch all configured USA and euro-area series, calculate every complete period,
# and persist raw payloads, normalized observations, revisions, and results.
.venv/bin/flask --app app data sync

# Narrow refreshes are useful during development or incident recovery.
.venv/bin/flask --app app data sync --geography USA --indicator headline_consumer_inflation

# Fetch and validate without writing data, or inspect the last stored run.
.venv/bin/flask --app app data verify --geography EA --indicator broad_money_expansion
.venv/bin/flask --app app data status
```

`data sync` exits 0 on success, 2 on a partial run, and 1 when every requested integration failed. Each provider has bounded retry/backoff for transient HTTP failures; a provider failure is recorded and does not discard successful provider data. Estimated or provisional observations remain usable but are explicitly marked and lower result confidence.

The cached read API is:

```text
GET /api/v1/country/{geography}/{indicator_id}?period=latest
GET /api/v1/country/{geography}/dashboard?period=latest
GET /api/v1/data/status
GET /api/v1/data/issues?run_id={optional-run-id}
GET /api/v1/data/lineage/{snapshot-id}
GET /api/v1/meta/data-sources
```

Configured cached indicators are `headline_consumer_inflation`, `essential_cost_inflation`, `broad_money_expansion`, and `economy_wide_inflation` for `USA` and `EA`. Cached GET routes enforce active `methodology_version` matching (per `CALCULATION_ENGINE_GUIDELINES.md` section 21) and emit conditional `ETag` / `Cache-Control` headers (`304 Not Modified` on `If-None-Match`). The same country-indicator URL continues to accept `POST` for caller-supplied normalized observations. SQLite defaults to `instance/inflation_lens.sqlite3`; override it with `INFLATION_DB_PATH`. Database files and secrets are ignored by Git.

The source mapping is declarative in `app/config/source_registry.yaml`. See [docs/DATA_INTEGRATION.md](docs/DATA_INTEGRATION.md) for provider behavior, storage lineage, and known data limitations.

## Strict calculation contract

Version `0.3.0` accepts normalized observations only. Anonymous numeric fields are rejected. A country request has this shape:

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

HTTP behavior: malformed contracts return 400, unknown geography/indicator 404, oversized bodies 413, validly shaped but uncomputable data 422, and rate-limited requests 429 (`RATE_LIMIT_EXCEEDED`). Dashboard routes return individual unavailable results rather than failing the entire dashboard.

### Security and rate limiting

- **Inbound rate limiting** (`app/api/rate_limit.py`): thread-safe, bounded-memory (`RATE_LIMIT_MAX_CLIENTS=4096`) sliding-window limiter with separate quotas for cached reads (`RATE_LIMIT_READ_PER_MINUTE=600`) and CPU-bound calculation `POST` routes (`RATE_LIMIT_CALC_PER_MINUTE=120`) over a `RATE_LIMIT_WINDOW_SECONDS=60` window. Emits `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`, and `Retry-After` headers. `GET /api/v1/health` and `OPTIONS` preflight requests are exempt. `X-Forwarded-For` is ignored unless `TRUST_PROXY_HEADERS=1` is explicitly set. Set `RATE_LIMIT_ENABLED=0` when running raw saturation load benchmarks (`perf/scripts/run.sh`).
- **HTTP security headers** (`app/factory.py`): every response sets `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'`, `Permissions-Policy: geolocation=(), microphone=(), camera=()`, and `Cross-Origin-Resource-Policy: cross-origin`.
- **Credential and path protection**: provider URLs must use `https://`, credentials (`api_key`, `UserID`, `token`, etc.) are scrubbed from both URLs (`sanitize_url`) and exception messages (`sanitize_text`) before logging or persistence in `sync_issues`, and country profile loading validates geography codes against `^[A-Z0-9_-]{2,16}$` without exposing host filesystem paths on 404 errors.

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
