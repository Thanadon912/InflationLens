# Official Data Integration

## Pipeline and trust boundary

`flask data sync` is the only path that calls external providers. It loads the reviewed source registry, fetches provider payloads through a retrying client, validates provider-specific schemas, stores gzip-compressed raw responses with SHA-256 hashes, normalizes observations, derives year-over-year inputs where required, invokes the existing strict calculation engine, and stores immutable result snapshots. GET requests only read those snapshots.

The SQLite lineage chain is:

```text
sync_runs -> raw_responses -> normalized_observations
                              -> observation_lineage (derived YoY inputs)
          -> indicator_results
          -> sync_issues
```

Raw responses, normalized revisions, and calculated snapshots are append-only. A changed value for the same series and period is retained as a new observation and marked `is_revised`. URLs containing credentials are sanitized before persistence; API status exposes only the database filename, not its host path.

## Configured official sources

| Geography | Lens | Primary source | Series/dataset |
|---|---|---|---|
| USA | Headline consumer | BLS | `CUUR0000SA0` |
| USA | Headline cross-check | FRED | `CPIAUCNS` |
| USA | Essential cost | BLS | Food, shelter, energy, transport, medical care, communications CPI series |
| USA | Broad money | FRED | `M2SL` |
| USA | Economy-wide | BEA | NIPA tables T10105/T10106, line 1 |
| EA20 | Headline/essential | Eurostat | `prc_hicp_minr`, 2025-base HICP |
| EA20 | Broad money | ECB Data Portal | BSI M3 stock series |
| EA20 | Economy-wide | Eurostat | `namq_10_gdp`, current and chain-linked volume GDP |
| USA/EA | Geography metadata | World Bank | `SP.POP.TOTL` (available for later global weighting) |

The registry deliberately fixes providers and series; runtime code does not choose sources dynamically. BLS/FRED headline indexes are cross-checked within the configured tolerance and discrepancies become sync issues.

## Result semantics

- Missing provider values are skipped, never converted to zero.
- Calculation runs only for periods with enough validated inputs under the engine's coverage rules.
- The cached `latest` result means the latest **complete calculable** period, not necessarily the newest period returned by one source.
- Provider estimates and provisional ECB observations set `is_estimated` and reduce confidence.
- Staleness is computed at read time using monthly/quarterly thresholds from the registry.
- Partial optional inputs are declared in coverage/warnings; for example, current broad-money snapshots do not yet add population or real-GDP diagnostics, and economy-wide snapshots currently calculate the GDP deflator rather than a domestic-demand deflator.

## Live verification on 2026-08-13

All eight geography/lens mappings completed against their real providers in incremental syncs and were served successfully through the cached Flask API. The live smoke database was local and is excluded from Git.

Two real-data edge cases changed or confirmed behavior:

1. BLS can encode a missing monthly value as `-`; the adapter now discards it instead of coercing it to zero.
2. Eurostat can publish an incomplete newest month across essential categories. At verification time, EA July 2026 had only one configured category, so the API correctly returned June 2026 as the latest complete essential-cost result.

The old Eurostat HICP dataset referenced in the planning guide, `prc_hicp_midx`, has been replaced by `prc_hicp_minr` with `coicop18` classifications and the 2025 index base. That schema was verified against the live response and is pinned in the registry.
