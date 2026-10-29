# Inflation Lens

A multi-dimensional inflation engine: a deterministic Python/Flask API that computes ten country-level and eight global inflation lenses from normalized economic observations, paired with a React 19 + TypeScript + Vite front end that visualizes them.

Instead of reporting a single "official" inflation number, it exposes the different ways inflation can be measured -- headline consumer prices, a fixed real-world basket, excess money growth, housing and asset prices, producer-price pressure, and more -- so the trade-offs between methodologies are visible rather than hidden behind one index.

## What's in here

| | |
|---|---|
| **Back-end/** | Flask API, calculation engines, official-data ingestion (FRED, BEA, BLS, Eurostat, ECB, World Bank), SQLite-cached reads, and in-memory HTTP rate limiting. See [Back-end/README.md](Back-end/README.md). |
| **Front-end/** | React 19 + TypeScript + Vite landing page and interactive workbench (`d3-geo` + `topojson-client`). Playwright end-to-end tests exercise the production bundle against a real running backend. |
| **perf/** | k6 load tests against a gunicorn-served API, with a Grafana dashboard built for QA. See [perf/README.md](perf/README.md). |
| **docs/** | Methodology references: calculation engine guidelines, country and global inflation methods, official data source guide. |

## Highlights

- **Strict, versioned calculation contract.** The API accepts only normalized, provenance-tagged observations -- no anonymous numbers -- and rejects malformed or under-covered input rather than silently approximating it.
- **Real official data, cached deterministically.** A CLI ingestion pipeline pulls from official providers, stores raw payloads and revisions with full lineage, and the web API only ever reads the cache -- so `GET` requests stay fast and deterministic even if a provider is slow or down.
- **Heavily tested.** 700+ backend tests (unit, property-based, integration, contract) at 97%+ branch coverage, plus a Playwright end-to-end suite that drives the real front end against a real Flask instance.
- **Measured, not assumed.** A k6 suite (smoke/load/stress/spike/abuse) drives the API on gunicorn against a production-sized seeded cache, with SLOs enforced by exit code and results in a purpose-built Grafana dashboard -- so "how fast" and "where it breaks" are answered numbers, not guesses. Measured: the read path saturates at **~700 req/s around 70 concurrent users** (4 gunicorn workers), and past that it queues rather than failing -- **0 errors in 303,343 requests** at 200 users. The ceiling scales with the worker pool, so it is a configuration limit, not a code one. Refusing a bad request costs about **a tenth** of serving a good one (p95 1.18 ms against 10.04 ms), so malformed traffic is not a cheaper way to exhaust it than ordinary traffic.
- **Documented methodology.** Every formula, weight, and edge case (missing components, coverage thresholds, quality adjustments) is written down in `docs/` and traced to its tests in `Back-end/docs/FORMULA_TRACE.md`.

## What's covered, and what isn't

**Covered**
- All 10 country lenses and 8 global lenses are fully implemented calculation engines, reachable via `POST` with any caller-supplied normalized observations that satisfy the contract -- not just the two geographies below.
- Automated official-data ingestion (`flask data sync`) is wired for **4 indicators × 2 geographies**: `headline_consumer_inflation`, `essential_cost_inflation`, `broad_money_expansion`, and `economy_wide_inflation`, for `USA` and `EA` only. Everything else (the other 6 country lenses, all 8 global lenses, any other country) works, but you supply the input data yourself.
- Ingested history depth follows each source's configured backfill window (24 months / 8 quarters by default) -- not a full historical archive.
- Contract validation, coverage thresholds, provenance/audit trail, and the documented methodology edge cases (missing components, structural dominance, quality adjustments) are all enforced and tested.

**Not covered**
- Model-based underlying inflation and the global common-factor model are explicitly out of scope for v1 (documented, not just missing).
- No auth or multi-tenancy -- the API is open by design for read/calculation queries, protected by bounded in-memory per-IP rate limiting (`read` and `calc` buckets, configurable via environment variables) and strict HTTP security headers.
- No production deployment setup: no HTTPS termination, no runtime monitoring or alerting. `perf/` does ship a containerized Prometheus/Grafana stack (bound to `127.0.0.1`) and a gunicorn config, but only for load testing -- the app itself is still not packaged for deployment. SQLite is used as the cache store; the load tests in `perf/` exercise the read path only (they saturate on gunicorn's worker pool, not on the database), so this store is still unproven under the concurrent **write** load a production ingestion schedule would put on it.
- CI runs on every pull request: the backend suite behind its coverage gate (`.github/workflows/backend-ci.yml`), the Playwright E2E suite against a real Flask process (`.github/workflows/e2e-ci.yml`), and dependency/secret/SAST scanning (`.github/workflows/security.yml`). Merging to `main` triggers CD directly without repeating CI (`.github/workflows/cd.yml`), deploying and promoting the Git-connected Vercel projects (`inflation-lens-api-thanadon912` and `inflation-lens-thanadon912`) via `scripts/vercel/manage.py`. The live-provider and load-test jobs run on a schedule instead, each for a reason documented in its workflow.

## Running it locally

```bash
# Back end
cd Back-end
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/flask --app app run --port 5000

# Front end (separate terminal, from Front-end/)
cd Front-end
npm install
npm run dev
# open http://localhost:3000/index.html
```

The front end talks to the API at `localhost:5000` by default. Full setup (env vars, data ingestion, test commands) is documented in [Back-end/README.md](Back-end/README.md).

## Project status

This is a **personal portfolio project** -- built to demonstrate engineering and system-design work, not shipped or operated as a product. It's in a genuinely working state (real data, real tests, a real end-to-end flow), but it isn't actively maintained as ongoing work, and there's no guarantee of future updates, support, or issue triage.

If you find it useful as a starting point, feel free to fork it and take it in your own direction.

## License

MIT -- see [LICENSE](LICENSE).
