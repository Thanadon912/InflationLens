---
title: Inflation Calculation Engine Guidelines
document_id: inflation-calculation-engine-guidelines
version: 1.0.0
status: draft
language: en
last_reviewed: 2026-08-02
applies_to:
  country_indicators: 10
  global_indicators: 8
related_documents:
  - COUNTRY_INFLATION_METHODS.md
  - GLOBAL_INFLATION_METHODS.md
  - API_DATA_SOURCES_GUIDE.md
---

# Inflation Calculation Engine Guidelines

## 1. Purpose

This document defines the engineering and governance rules for implementing the inflation calculation engine.

The engine must support:

### Country-level indicators

1. Headline Consumer Inflation
2. Underlying Inflation
3. Essential Cost Inflation
4. Fixed-Lifestyle Inflation
5. Housing Inflation
6. Broad Money Expansion
7. Excess Money Growth
8. Producer and Import Inflation
9. Economy-Wide Inflation
10. Purchasing-Power Squeeze

### Global indicators

1. Global Consumer Inflation
2. Median Country Inflation
3. Global Essential Inflation
4. Global Monetary Expansion
5. Global Excess Money Growth
6. Global Producer Pressure
7. Global Housing and Asset Inflation
8. Global Inflation Synchronization

The calculation engine must be deterministic, auditable, source-independent, and isolated from AI-generated decisions.

---

# 2. Core Design Principle

The engine must separate four concerns:

```text
External APIs
    ↓
Provider adapters
    ↓
Normalized observations
    ↓
Calculation engine
    ↓
Validated indicator results
```

The calculation engine must never:

- call external APIs directly;
- search for series dynamically;
- select a provider;
- infer a missing source;
- change a formula based on the result;
- ask an AI model to calculate a value;
- silently interpolate missing data;
- hide methodology differences.

The engine may only consume validated normalized inputs.

---

# 3. Required Architecture

## 3.1 Recommended package structure

```text
app/
├── engines/
│   ├── shared/
│   │   ├── growth.py
│   │   ├── aggregation.py
│   │   ├── validation.py
│   │   ├── coverage.py
│   │   ├── standardization.py
│   │   └── errors.py
│   │
│   ├── country/
│   │   ├── headline_consumer.py
│   │   ├── underlying.py
│   │   ├── essential_cost.py
│   │   ├── fixed_lifestyle.py
│   │   ├── housing.py
│   │   ├── broad_money.py
│   │   ├── excess_money.py
│   │   ├── producer_import.py
│   │   ├── economy_wide.py
│   │   └── purchasing_power.py
│   │
│   └── global/
│       ├── consumer.py
│       ├── median_country.py
│       ├── essential.py
│       ├── monetary.py
│       ├── excess_money.py
│       ├── producer_pressure.py
│       ├── housing_assets.py
│       └── synchronization.py
│
├── models/
│   ├── observation.py
│   ├── indicator_result.py
│   ├── quality.py
│   ├── methodology.py
│   └── coverage.py
│
├── providers/
│   ├── bls.py
│   ├── bea.py
│   ├── fred.py
│   ├── eurostat.py
│   ├── ecb.py
│   ├── world_bank.py
│   ├── bis.py
│   └── imf.py
│
├── config/
│   ├── source_registry.yaml
│   ├── indicator_registry.yaml
│   ├── methodology_versions.yaml
│   ├── global_weights.yaml
│   └── country_profiles/
│       ├── USA.yaml
│       ├── EA.yaml
│       └── ...
│
└── tests/
    ├── unit/
    ├── integration/
    ├── regression/
    ├── fixtures/
    └── snapshots/
```

## 3.2 Module responsibility

Each engine module should contain:

- input validation;
- deterministic formula execution;
- quality and coverage calculation;
- output assembly;
- no network logic;
- no database logic;
- no UI formatting logic.

---

# 4. Normalized Observation Contract

Every input must conform to a common schema.

```json
{
  "provider": "bls",
  "source_series_id": "CUUR0000SA0",
  "indicator_id": "headline_consumer_inflation",
  "geography": "USA",
  "frequency": "monthly",
  "unit": "index",
  "seasonally_adjusted": false,
  "observation_period": "2026-06",
  "value": 321.5,
  "retrieved_at": "2026-08-02T12:00:00Z",
  "publication_date": "2026-07-15",
  "source_url": "https://www.bls.gov/",
  "is_estimated": false,
  "is_revised": false,
  "validation_status": "validated",
  "methodology_version": "1.0.0"
}
```

## 4.1 Required fields

- provider
- source series ID
- normalized indicator ID
- geography
- frequency
- unit
- observation period
- numeric value
- retrieval timestamp
- validation status

## 4.2 Optional but recommended fields

- publication date
- seasonal-adjustment status
- source URL
- estimate flag
- revision flag
- data-vintage identifier
- source methodology version
- confidence level
- coverage status

---

# 5. Unit System

## 5.1 Allowed unit categories

The engine should use controlled unit identifiers.

Examples:

```text
index
percent_yoy
percent_mom
percent_annualized
currency
currency_per_unit
local_currency
persons
households
ratio
share_percent
standard_deviation_score
```

## 5.2 Unit validation rule

A formula must declare its accepted input units.

Example:

```python
required_unit = "index"
```

If the input uses `percent_yoy`, the engine must reject it unless the formula explicitly accepts rates.

Example failure:

```text
Expected: index
Received: percent_yoy
Action: raise UnitMismatchError
```

## 5.3 No silent conversions

Conversions must be explicit and traceable.

Permitted:

```text
monthly index → year-over-year rate
```

Not permitted:

```text
annual inflation rate → reconstructed monthly index
```

unless a documented estimation model is used and the result is marked estimated.

---

# 6. Frequency and Period Alignment

## 6.1 Supported frequencies

- daily
- weekly
- monthly
- quarterly
- annual

## 6.2 Frequency compatibility

A formula must define the expected frequency.

Examples:

- CPI YoY: monthly index preferred
- GDP deflator: quarterly or annual
- broad money: monthly preferred
- house-price index: quarterly accepted
- wages: monthly, quarterly, or annual depending on source

## 6.3 Mixed-frequency rule

Never combine data of different frequencies without an explicit alignment policy.

Allowed options:

1. convert all data to the lowest shared frequency;
2. use trailing-twelve-month growth;
3. preserve native frequencies and return separate values;
4. use an estimated mixed-frequency model with an estimate flag.

## 6.4 Period-alignment rule

Inputs must refer to the same economic period or an explicitly documented lag.

Example:

```text
Money growth: 2026 Q2
Real GDP growth: 2026 Q2
```

Invalid without disclosure:

```text
Money growth: June 2026
Real GDP growth: Q1 2026
```

---

# 7. Shared Formula Utilities

## 7.1 Year-over-year growth

\[
g^{YoY}_t
=
\left(
\frac{X_t}{X_{t-k}}-1
\right)\times100
\]

where:

- \(k=12\) for monthly data;
- \(k=4\) for quarterly data;
- \(k=1\) for annual data.

## 7.2 Period-over-period growth

\[
g_t
=
\left(
\frac{X_t}{X_{t-1}}-1
\right)\times100
\]

## 7.3 Annualized growth

For monthly data:

\[
g^{Ann}_t
=
\left[
\left(
\frac{X_t}{X_{t-1}}
\right)^{12}-1
\right]\times100
\]

For quarterly data:

\[
g^{Ann}_t
=
\left[
\left(
\frac{X_t}{X_{t-1}}
\right)^4-1
\right]\times100
\]

## 7.4 Exact real growth adjustment

\[
g^{real}
=
\left[
\frac{1+g^{nominal}}
{1+\pi}
-1
\right]\times100
\]

Rates inside the fraction must be expressed as decimals.

## 7.5 Weighted arithmetic mean

\[
A
=
\sum_i w_ix_i
\]

subject to:

\[
\sum_iw_i=1
\]

## 7.6 Weighted geometric mean

\[
G
=
\prod_i
(1+x_i)^{w_i}-1
\]

Rates must be expressed as decimals inside the product.

## 7.7 Weighted median

Sort values \(x_{(i)}\) by ascending order and find the first value satisfying:

\[
\sum_{j\le i}w_{(j)}\ge0.5
\]

## 7.8 Z-score

\[
z_i
=
\frac{x_i-\mu_i}{\sigma_i}
\]

Z-scores may be used only for analytical scores, not inflation rates.

---

# 8. Country Engine Requirements

# 8.1 Headline Consumer Inflation

## Inputs

- all-items CPI index
- period
- frequency
- seasonal-adjustment metadata

## Required outputs

- year-over-year inflation
- period-over-period inflation
- optional annualized momentum
- source period
- quality flags

## Validation

- input must be an index;
- sufficient history must exist;
- no zero or negative index values;
- periods must be continuous or gaps disclosed.

---

# 8.2 Underlying Inflation

## Supported methods

- official core inflation
- weighted median
- trimmed mean
- model-based common factor

## Rule

The engine must not choose a method based on whichever produces the lowest or highest result.

The selected method must come from configuration.

```yaml
underlying_inflation:
  preferred_method: weighted_median
  fallback_methods:
    - trimmed_mean
    - official_core
```

## Required outputs

```json
{
  "selected_method": "weighted_median",
  "selected_value": 3.4,
  "core_value": 3.1,
  "trimmed_mean_value": 3.3,
  "weighted_median_value": 3.4
}
```

Unavailable methods must be returned as unavailable, not omitted silently.

---

# 8.3 Essential Cost Inflation

## Inputs

- category price rates or indexes
- essential-category list
- category weights
- weight methodology
- basket version

## Weight rule

Weights must come from configuration or an official expenditure source.

Never hard-code universal weights inside calculation functions.

```yaml
essential_basket:
  version: "2026.1"
  methodology: lower_income_expenditure_weights
  categories:
    food: 0.24
    housing: 0.42
    energy: 0.08
    transport: 0.12
    healthcare: 0.09
    communications: 0.05
```

## Validation

- weights must be non-negative;
- weights must sum to one within tolerance;
- categories must match input series;
- missing categories require coverage reporting.

---

# 8.4 Fixed-Lifestyle Inflation

## Inputs

- reference-period item quantities
- current and reference prices
- product identity
- package size
- replacement status
- quality-adjustment status

## Required calculations

- fixed-basket price index
- item-level contribution
- shrinkflation-adjusted unit price
- replacement coverage
- quality confidence

## Rules

- do not replace a discontinued item silently;
- preserve original item identity;
- record replacement hierarchy;
- return a lower confidence score when proxies are used.

---

# 8.5 Housing Inflation

## Required sub-results

- rent inflation
- house-price inflation
- mortgage-payment inflation
- housing burden

## Rule

Do not average these into one inflation rate by default.

Optional housing pressure scores must be labeled as scores.

```json
{
  "rent_inflation": 4.1,
  "house_price_inflation": 6.8,
  "mortgage_payment_inflation": 12.3,
  "housing_burden_percent": 34.5
}
```

## Mortgage assumptions

Mortgage calculations must receive assumptions from configuration:

- loan-to-value ratio
- loan term
- repayment frequency
- representative mortgage rate
- representative property price

Assumptions must be returned in result metadata.

---

# 8.6 Broad Money Expansion

## Inputs

- official broad-money level
- aggregate definition
- monthly or quarterly observations

## Required outputs

- YoY money growth
- per-capita money growth where possible
- money-to-real-output ratio
- aggregate definition

## Rule

Never label broad-money growth as consumer inflation.

Preferred label:

```text
Broad Money Expansion
```

---

# 8.7 Excess Money Growth

## Inputs

- broad-money growth
- real-output growth
- optional velocity change

## Outputs

Simple:

\[
EMG=g(M)-g(Y)
\]

Velocity-adjusted:

\[
MP=g(M)+g(V)-g(Y)
\]

## Rules

- periods must be aligned;
- weight or frequency mismatches must be rejected;
- result must be described as monetary pressure, not guaranteed price inflation.

---

# 8.8 Producer and Import Inflation

## Inputs

- PPI
- import-price index
- exchange rate
- energy prices
- commodity prices
- configured component weights

## Outputs

- PPI inflation
- import-price inflation
- exchange-rate contribution
- optional upstream pressure score

## Rule

A standardized score is not an inflation rate.

Pass-through to consumers must not be assumed to be one-to-one.

---

# 8.9 Economy-Wide Inflation

## Supported methods

- GDP deflator
- domestic-demand deflator

## Required outputs

Return both where available.

```json
{
  "gdp_deflator_inflation": 3.8,
  "domestic_demand_deflator_inflation": 4.2
}
```

## Rule

Do not average the two automatically because they answer different economic questions.

---

# 8.10 Purchasing-Power Squeeze

## Inputs

- nominal wage or income growth
- headline inflation
- essential-cost inflation
- income definition

## Required outputs

- headline-CPI-adjusted real wage growth
- essential-cost-adjusted real wage growth
- optional disposable-income-adjusted growth
- purchasing-power squeeze

## Rules

- preserve mean versus median wage definition;
- preserve gross versus disposable income definition;
- do not mix household and individual income without disclosure.

---

# 9. Global Engine Requirements

# 9.1 Global Consumer Inflation

## Inputs

- validated country headline inflation or price relatives
- country weights
- weight method
- coverage metadata

## Supported aggregation

- arithmetic weighted mean
- geometric chained index

## Preferred default

Household-consumption PPP weights.

## Required outputs

- global rate
- weight method
- included-country count
- population coverage
- GDP coverage
- consumption coverage
- missing-country list

---

# 9.2 Median Country Inflation

## Required outputs

- unweighted median
- optional weighted median
- 25th percentile
- 75th percentile
- minimum
- maximum
- number of countries

## Rule

Do not remove hyperinflation observations unless they are verified data errors.

---

# 9.3 Global Essential Inflation

## Inputs

- country essential-cost inflation
- common taxonomy mapping
- global weights
- category-coverage metadata

## Rule

Country-level essential indicators must be calculated before global aggregation.

Do not aggregate raw category labels without taxonomy normalization.

---

# 9.4 Global Monetary Expansion

## Inputs

- country broad-money growth in local-currency terms
- GDP PPP or configured weights

## Rule

Do not convert national money stocks into USD before calculating the default growth measure.

Currency conversion may be a separate analytical view.

---

# 9.5 Global Excess Money Growth

## Supported approaches

### Country-first

\[
GEMG
=
\sum_cw_c
\left[
g(M_c)-g(Y_c)
\right]
\]

### Aggregate-first

\[
GEMG
=
GME-g(Y^G)
\]

The selected method must be configured and returned in metadata.

---

# 9.6 Global Producer Pressure

## Inputs

- global or country PPI
- import-price measures
- commodity indexes
- logistics indexes
- energy measures

## Rule

Because units and volatility differ, a combined result must normally be a standardized pressure score.

It must not be labeled an inflation rate.

---

# 9.7 Global Housing and Asset Inflation

## Required separation

Return distinct measures for:

- rent
- house prices
- equities
- gold
- Bitcoin
- other configured assets

## Rule

Asset returns must remain separate from consumer inflation.

A combined asset-pressure score is optional but must disclose standardization and weights.

---

# 9.8 Global Inflation Synchronization

## Supported outputs

- share of countries above threshold
- population-weighted share above threshold
- share of countries with accelerating inflation
- cross-country standard deviation
- interquartile range
- optional common-factor result

## Rules

- threshold values must be configurable;
- country count and coverage must always be returned;
- the common-factor model must be versioned separately.

---

# 10. Missing Data Policy

## 10.1 Default behavior

Missing data should remain missing.

The engine must not invent values.

## 10.2 Permitted responses

- unavailable
- partial coverage
- stale
- estimated
- low confidence

## 10.3 Weight renormalization

Weights may be renormalized only when:

- coverage exceeds a configured threshold;
- missing components are not structurally dominant;
- the result is labeled partial;
- original and adjusted weights are stored.

\[
w_i^*
=
\frac{w_i}
{\sum_{j\in A}w_j}
\]

## 10.4 Global coverage thresholds

Suggested defaults:

```yaml
global_coverage:
  consumer_consumption_ppp_minimum: 0.85
  macro_gdp_ppp_minimum: 0.85
  population_minimum: 0.80
```

---

# 11. Configuration Rules

The following values must remain outside calculation code:

- source priorities
- series IDs
- basket categories
- basket weights
- trim percentages
- monetary aggregate choice
- mortgage assumptions
- global weight method
- coverage thresholds
- synchronization thresholds
- standardization windows
- composite-score weights
- fallback methods

## 11.1 Example country profile

```yaml
country: USA
profile_version: "1.0.0"

headline_consumer:
  source_indicator: headline_consumer_inflation

underlying:
  preferred_method: official_core
  fallback_methods:
    - trimmed_mean
    - weighted_median

money:
  preferred_aggregate: M2

essential_basket:
  version: "2026.1"
  categories:
    food: 0.24
    housing: 0.42
    energy: 0.08
    transport: 0.12
    healthcare: 0.09
    communications: 0.05

housing:
  mortgage_term_years: 30
  loan_to_value: 0.80
  payment_frequency: monthly
```

---

# 12. Result Contract

Every indicator result must expose both value and context.

```json
{
  "indicator_id": "headline_consumer_inflation",
  "geography": "USA",
  "period": "2026-06",
  "value": 3.2,
  "unit": "percent_yoy",
  "method": "index_year_over_year",
  "methodology_version": "1.0.0",
  "input_series": [
    {
      "provider": "bls",
      "series_id": "CUUR0000SA0"
    }
  ],
  "coverage": "full",
  "confidence": "high",
  "is_estimated": false,
  "warnings": [],
  "calculated_at": "2026-08-02T12:00:00Z"
}
```

## 12.1 Required result fields

- indicator ID
- geography
- observation period
- value
- unit
- calculation method
- methodology version
- input provenance
- coverage
- confidence
- estimate flag
- warnings
- calculation timestamp

---

# 13. Error Handling

Use explicit domain errors.

Recommended errors:

```text
UnitMismatchError
FrequencyMismatchError
PeriodAlignmentError
InsufficientHistoryError
InvalidWeightError
CoverageThresholdError
MissingRequiredInputError
UnsupportedMethodError
SeriesDefinitionError
DataQualityError
```

Example:

```python
raise UnitMismatchError(
    expected="index",
    received="percent_yoy",
    indicator="headline_consumer_inflation"
)
```

Do not return zero when calculation fails.

---

# 14. Quality and Confidence

## 14.1 Suggested confidence levels

### High

- official source
- direct series match
- complete coverage
- no estimates
- current data
- validated metadata

### Medium

- reputable international fallback
- minor mapping assumptions
- partial category coverage
- moderate publication lag

### Low

- estimated
- stale
- incomplete
- proxy series
- unresolved methodology mismatch

## 14.2 Confidence must not change the numeric value

Confidence is metadata, not a formula adjustment.

---

# 15. Testing Requirements

## 15.1 Unit tests

Every formula requires tests for:

- normal input
- zero growth
- negative growth
- missing history
- invalid unit
- invalid frequency
- zero denominator
- negative or zero index
- weights not summing to one
- partial coverage
- extreme inflation
- deflation

## 15.2 Property tests

Examples:

- identical prices should produce zero inflation;
- multiplying all basket quantities by the same constant should not change a price index;
- weighted means must stay within the minimum and maximum input values when weights are valid;
- a median must not depend on country order;
- global results must be invariant to input ordering;
- renormalized weights must sum to one.

## 15.3 Regression tests

Store known fixture outputs.

Example:

```text
fixture: usa_cpi_2025_2026
expected_yoy: 3.200000
tolerance: 0.000001
```

A methodology change must intentionally update snapshots.

## 15.4 Integration tests

Verify:

- provider adapter output matches normalized schema;
- source registry mapping exists;
- frequency and units are correct;
- engine accepts valid normalized observations;
- provenance survives through the result.

## 15.5 Cross-source comparison tests

Where two reputable providers report the same concept:

- compare values within a tolerance;
- flag unexplained differences;
- do not automatically replace the primary source.

---

# 16. Numerical Precision

## 16.1 Internal precision

Use decimal or high-precision numeric operations where weights and chained indexes are involved.

## 16.2 Display precision

Recommended:

- rates: 1–2 decimal places
- index values: source-appropriate precision
- weights: at least 4 decimal places internally
- coverage: 1 decimal place
- scores: 1 decimal place

## 16.3 No early rounding

Do not round intermediate calculations.

Round only at the presentation layer.

---

# 17. Revisions and Data Vintages

The engine should preserve:

- original observation;
- revised observation;
- retrieval timestamp;
- source publication date;
- vintage identifier where available.

A historical chart should disclose whether it uses:

- latest revised history;
- real-time vintage history;
- mixed vintages.

---

# 18. AI Separation and Bias Control

AI may:

- explain results;
- translate country names;
- suggest candidate data mappings;
- summarize methodology;
- describe missing coverage.

AI must not:

- calculate official values;
- set weights;
- select formulas;
- select sources after seeing results;
- fabricate observations;
- fill missing values;
- override validation failures;
- label a pressure score as inflation.

Production mappings must come from reviewed configuration.

---

# 19. Composite Scores

Composite scores are optional.

They must not be called:

```text
True Inflation
```

Acceptable names include:

- Inflation Pressure Score
- Cost and Monetary Pressure Index
- Inflation Conditions Score

## 19.1 Standardization

\[
z_{i,t}
=
\frac{x_{i,t}-\mu_i}{\sigma_i}
\]

## 19.2 Composite

\[
Score_t
=
\sum_iw_iz_{i,t}
\]

## 19.3 Required disclosures

- components
- weights
- standardization window
- missing-data treatment
- methodology version
- coverage

---

# 20. Logging and Audit Trail

Every calculation should log:

- indicator ID
- geography
- method
- input series
- input periods
- configuration version
- methodology version
- warnings
- output
- timestamp
- software version or Git commit

Example:

```json
{
  "event": "indicator_calculated",
  "indicator_id": "broad_money_expansion",
  "geography": "USA",
  "period": "2026-06",
  "methodology_version": "1.0.0",
  "config_version": "usa-1.0.0",
  "git_commit": "abc1234",
  "warnings": []
}
```

---

# 21. Performance and Caching

The engine should be pure and fast.

Recommended caching layers:

1. raw provider response cache
2. normalized observation cache
3. indicator-result cache

Cache keys should include:

- geography
- indicator
- period
- methodology version
- configuration version
- source data vintage

A methodology change must invalidate affected calculated results.

---

# 22. Security

- Keep secrets in backend environment variables.
- Never send provider tokens to the frontend.
- Do not log secrets.
- Validate all external payloads.
- Limit file and network access in calculation workers.
- Treat provider text metadata as untrusted input.
- Escape content before rendering in UI.

---

# 23. Definition of Done

An indicator implementation is complete only when:

1. formula matches the methodology document;
2. accepted units are declared;
3. frequency rules are declared;
4. configuration is externalized;
5. normalized input schema is enforced;
6. output schema is enforced;
7. provenance is preserved;
8. missing-data behavior is defined;
9. confidence and coverage are returned;
10. unit tests pass;
11. regression fixtures exist;
12. documentation is updated;
13. methodology version is recorded;
14. no AI is involved in numeric calculation.

---

# 24. Initial Implementation Order

Recommended sequence:

## Shared foundation

1. normalized observation model
2. indicator result model
3. validation utilities
4. growth formulas
5. weighted aggregation
6. coverage calculation
7. error classes

## Country engines

1. Headline Consumer Inflation
2. Broad Money Expansion
3. Economy-Wide Inflation
4. Purchasing-Power Squeeze
5. Essential Cost Inflation
6. Underlying Inflation
7. Excess Money Growth
8. Producer and Import Inflation
9. Housing Inflation
10. Fixed-Lifestyle Inflation

## Global engines

1. Median Country Inflation
2. Global Consumer Inflation
3. Global Monetary Expansion
4. Global Excess Money Growth
5. Global Inflation Synchronization
6. Global Essential Inflation
7. Global Producer Pressure
8. Global Housing and Asset Inflation

The more experimental indicators should be implemented after the foundational formulas and validation framework are stable.

---

# 25. Final Rule

The engine must make every result reproducible.

The required traceability chain is:

```text
Displayed value
→ indicator result
→ calculation method
→ methodology version
→ configuration version
→ normalized observations
→ provider series
→ raw provider response
→ official source
```

If any part of this chain is missing, the result must not be marked validated.
