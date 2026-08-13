# Formula Trace and Definition of Done

Verified against `CALCULATION_ENGINE_GUIDELINES.md`, `COUNTRY_INFLATION_METHODS.md`, and `GLOBAL_INFLATION_METHODS.md`. Snapshot values are independently fixed in `tests/snapshots/formula_outputs.yaml` with absolute tolerance `1e-9`.

| Indicator | Methodology | Implementation | Regression proof | Status |
|---|---|---|---|---|
| Headline Consumer Inflation | Country §4; Engine §8.1 | `country/headline_consumer.py::calculate` | `headline_consumer_inflation` | verified |
| Underlying Inflation | Country §5; Engine §8.2 | `country/underlying.py::calculate` | `underlying_inflation` | verified; model factor unavailable v1 |
| Essential Cost Inflation | Country §6; Engine §8.3 | `country/essential_cost.py` | `essential_cost_inflation` | verified |
| Fixed-Lifestyle Inflation | Country §7; Engine §8.4 | `country/fixed_lifestyle.py::calculate` | `fixed_lifestyle_inflation` | verified |
| Housing Inflation | Country §8; Engine §8.5 | `country/housing.py::calculate` | `housing_inflation` | verified; components remain separate |
| Broad Money Expansion | Country §9; Engine §8.6 | `country/broad_money.py::calculate` | `broad_money_expansion` | verified |
| Excess Money Growth | Country §10; Engine §8.7 | `country/excess_money.py::calculate` | `excess_money_growth` | verified |
| Producer and Import Inflation | Country §11; Engine §8.8 | `country/producer_import.py::calculate` | `producer_import_inflation` | verified |
| Economy-Wide Inflation | Country §12; Engine §8.9 | `country/economy_wide.py::calculate` | `economy_wide_inflation` | verified; deflators remain separate |
| Purchasing-Power Squeeze | Country §13; Engine §8.10 | `country/purchasing_power.py::calculate` | `purchasing_power_squeeze` | verified |
| Global Consumer Inflation | Global §5; Engine §9.1 | `global_/consumer.py::calculate` | `global_consumer_inflation` | verified; arithmetic and geometric chain supported |
| Median Country Inflation | Global §6; Engine §9.2 | `global_/median_country.py::calculate` | `median_country_inflation` | verified; hyperinflation retained |
| Global Essential Inflation | Global §7; Engine §9.3 | `global_/essential.py::calculate` | `global_essential_inflation` | verified; consumes country-level normalized result |
| Global Monetary Expansion | Global §8; Engine §9.4 | `global_/monetary.py::calculate` | `global_monetary_expansion` | verified; local-currency rates only |
| Global Excess Money Growth | Global §9; Engine §9.5 | `global_/excess_money.py::calculate` | `global_excess_money_growth` | verified |
| Global Producer Pressure | Global §10; Engine §9.6 | `global_/producer_pressure.py::calculate` | `global_producer_pressure` | verified; composite is a score |
| Global Housing and Asset Inflation | Global §11; Engine §9.7 | `global_/housing_assets.py::calculate` | `global_housing_asset_inflation` | verified; assets remain separate |
| Global Inflation Synchronization | Global §12; Engine §9.8 | `global_/synchronization.py::calculate` | `global_inflation_synchronization` | verified; dispersion is subtracted |

## Shared formulas

Growth, exact real adjustment and log change are in `shared/growth.py`; weighted arithmetic/geometric aggregation, median, percentile, trimmed mean, Laspeyres and chain linking are in `shared/aggregation.py`; z-scores/composites are in `shared/standardization.py`; coverage thresholds and weight renormalization are in `shared/coverage.py`. Property tests prove scale/order invariants and weight normalization.

## Definition of Done audit

All 18 indicators satisfy the 14 Engine §23 checks:

1. Formula is mapped above and protected by a known-output snapshot.
2. Accepted input units are enforced by the strict request-role contract.
3. Native frequency and explicit historical/weight lag rules are enforced.
4. Policy, basket, composite and threshold values are externalized in YAML.
5. Only normalized, validated observations cross the API boundary.
6. Frozen result/component dataclasses enforce the output contract.
7. Provider, series, URL, vintage and retrieval provenance survive to output.
8. Missing inputs become explicit errors or unavailable dashboard results.
9. Every result contains confidence and coverage; every global result has a coverage report.
10. Unit/property/integration tests pass.
11. All 18 regression fixtures exist.
12. README and this trace document the implementation and deviations.
13. Methodology `1.0.1` and config versions are returned and audited.
14. Numeric calculation is deterministic code only; purity tests forbid network/database/config I/O in engines.

Current mismatch count: **0** for implemented v1 formulas. Explicitly out-of-scope statistical factor models remain unavailable rather than estimated.

## Verification evidence

Last verified on 2026-08-13 (Python 3.14.6):

- Full suite with branch coverage: 540 passed; `app/` coverage 95.12%.
- Property invariants: 13 passed.
- One fixed expected-output snapshot per indicator: 18 passed at absolute tolerance `1e-9`.
- Engine purity gates: 3 passed (network/database/config I/O, prohibited product labels, and hard-coded policy-weight mappings/defaults).
- Live Flask smoke: health, indicator metadata, and normalized USA headline calculation all returned HTTP 200; headline fixture returned 12.0% YoY.

The verification pass found and corrected three material failure modes in the inherited implementation: synchronization had added standardized dispersion instead of subtracting it; rejected observations could reach calculation; and empty synchronization/zero population inputs could escape as HTTP 500 errors. Regression and strict-contract tests now protect each correction.
