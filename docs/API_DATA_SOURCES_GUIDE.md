---
title: Inflation Data APIs and Integration Guide
document_id: inflation-api-data-sources-guide
version: 1.0.0
status: draft
language: en
last_reviewed: 2026-08-02
project_scope:
  - United States
  - European Union
  - Euro Area
  - Global expansion
  - Thailand expansion
---

# Inflation Data APIs and Integration Guide

## 1. Purpose

This document defines the external data providers used by the inflation dashboard project.

It explains:

- what each provider supplies;
- which project indicators it supports;
- whether registration or authentication is required;
- how the provider should be used;
- which sources are primary, fallback, optional, or deferred;
- how credentials and source mappings should be stored;
- how to prevent AI-generated source selection from introducing bias.

This document describes data acquisition only. Inflation formulas must remain in:

- `COUNTRY_INFLATION_METHODS.md`
- `GLOBAL_INFLATION_METHODS.md`

---

# 2. Current Project Status

## 2.1 Available now

- BLS API Version 1
- BEA API
- FRED API
- Eurostat API
- ECB Data Portal API
- World Bank Indicators API
- BIS Statistics API
- IMF Data API
- ILOSTAT
- OECD Data Explorer API
- TPSO Economic Index API
- EIA API
- CoinGecko API
- Alpha Vantage API

## 2.2 Available but needs integration verification

- FAOSTAT API: an access token is available, but the exact authentication header and quota must be confirmed from the developer portal.
- IMF Data API: the project owner verified that the selected endpoint works without authentication.

## 2.3 Not available or deferred

- BLS Version 2: registration is blocked by repeated CAPTCHA rejection.
- BOT API: registration and product subscription have not yet been completed.
- Nasdaq Data Link: account/API key not yet obtained.

None of these blocks the initial United States and EU/Euro Area demo.

---

# 3. Recommended Initial Architecture

```text
React frontend
    |
    v
Python backend API
    |
    +-- Provider adapters
    |     +-- BLS
    |     +-- BEA
    |     +-- FRED
    |     +-- Eurostat
    |     +-- ECB
    |     +-- World Bank
    |     +-- BIS
    |
    +-- Validation layer
    |
    +-- Normalized database
    |
    +-- Deterministic calculation engine
```

Authenticated providers must never be called directly from the browser.

---

# 4. Initial Demo Providers

| Priority | Provider | Main role | Authentication |
|---:|---|---|---|
| 1 | BLS | US consumer and producer prices | None for v1 |
| 2 | BEA | US national accounts and income | API key required |
| 3 | FRED | US money, credit, housing, and financial series | API key required |
| 4 | Eurostat | EU/Euro Area prices, wages, housing, and national accounts | None |
| 5 | ECB | Euro Area money, credit, rates, and exchange rates | None |
| 6 | World Bank | PPP, population, country metadata, and global weights | None |
| 7 | BIS | Comparable housing, credit, and financial-system data | None |

---

# 5. United States Providers

## 5.1 BLS Public Data API

### Official links

- https://www.bls.gov/developers/
- https://www.bls.gov/developers/api_faqs.htm
- https://www.bls.gov/developers/api_signature.htm
- https://www.bls.gov/developers/api_signature_v2.htm
- https://data.bls.gov/registrationEngine/

### What it provides

- CPI and CPI components
- headline and core CPI
- food, shelter, rent, and energy indexes
- PPI
- import/export price indexes
- average hourly earnings
- Employment Cost Index

### Indicators supported

- Headline Consumer Inflation
- Underlying Inflation
- Essential Cost Inflation
- Fixed-Lifestyle Inflation
- Housing Inflation
- Producer and Import Inflation
- Purchasing-Power Squeeze

### Authentication

**Version 1**

- Registration: no
- API key: no
- Status: available

**Version 2**

- Registration: yes
- Registration key: yes
- Status: blocked by CAPTCHA

### Published limits

| Limit | v1 | v2 |
|---|---:|---:|
| Daily queries | 25 | 500 |
| Series per query | 25 | 50 |
| Years per query | 10 | 20 |
| Requests per 10 seconds | 50 | 50 |
| Metadata | No | Yes |
| Server-side calculations | No | Yes |

### Initial decision

Use Version 1 and batch multiple series per POST request.

```text
https://api.bls.gov/publicAPI/v1/timeseries/data/
```

```json
{
  "seriesid": [
    "CUUR0000SA0",
    "CUUR0000SA0L1E",
    "CUUR0000SAF1",
    "CUUR0000SAH1"
  ],
  "startyear": "2017",
  "endyear": "2026"
}
```

Because v1 lacks full metadata, keep a reviewed local series registry.

```yaml
CUUR0000SA0:
  provider: bls
  title: Consumer Price Index for All Urban Consumers, All Items
  indicator_id: headline_consumer_inflation
  frequency: monthly
  seasonal_adjustment: not_seasonally_adjusted
  unit: index
```

### Rules

- Never guess a series ID.
- Store seasonal-adjustment status.
- Prefer index levels over precomputed growth rates.
- Split requests when more than ten years are needed.
- AI may suggest candidate series, but production mappings require review.

---

## 5.2 BEA API

### Official links

- https://apps.bea.gov/api/signup/
- https://apps.bea.gov/api/
- https://apps.bea.gov/api/_pdf/bea_web_service_api_user_guide.pdf

### What it provides

- PCE Price Index and core PCE
- nominal and real GDP
- GDP deflator
- personal income
- disposable personal income
- household consumption
- national and industry accounts

### Indicators supported

- Economy-Wide Inflation
- Excess Money Growth
- Purchasing-Power Squeeze
- PCE-versus-CPI comparison

### Authentication

- Registration: required
- Credential: 36-character UserID/API key
- Email activation: required
- Status: available

```env
BEA_API_KEY=
```

### Endpoint

```text
https://apps.bea.gov/api/data/
```

Example:

```text
https://apps.bea.gov/api/data/?UserID=YOUR_KEY&method=GETDATASETLIST&ResultFormat=JSON
```

### Rules

- Treat the UserID as a secret.
- Store table names, line codes, units, and frequency.
- Preserve retrieval timestamps because BEA data is revised.
- Do not mix annualized quarterly changes with YoY values without labeling.

---

## 5.3 FRED API

### Official links

- https://fred.stlouisfed.org/docs/api/fred/
- https://fred.stlouisfed.org/docs/api/fred/v2/api_key.html
- https://fred.stlouisfed.org/docs/api/fred/series_observations.html

### What it provides

- M2 and other monetary aggregates
- money velocity
- Federal Funds Rate
- mortgage rates
- house-price indexes
- bank credit
- Treasury yields
- inflation expectations
- commodity and financial series

### Indicators supported

- Broad Money Expansion
- Excess Money Growth
- Housing Inflation
- Global Housing and Asset Inflation
- monetary and financial context

### Authentication

- Account: required
- API key: required
- Status: available

```env
FRED_API_KEY=
```

### Rules

FRED is often a distributor, not the original producer.

Store:

- FRED series ID
- original source institution
- release name
- frequency
- unit
- seasonal adjustment
- last update date

Prefer direct BLS and BEA integrations where they already exist.

---

## 5.4 EIA Open Data API

### Official links

- https://www.eia.gov/opendata/documentation.php
- https://www.eia.gov/opendata/register.php

### What it provides

- gasoline and diesel prices
- electricity prices
- natural gas prices
- petroleum and energy production
- state-level energy data

### Indicators supported

- Essential Cost Inflation
- Producer and Import Inflation
- Global Producer Pressure

### Authentication

- API registration/key: required for normal API use
- Status: available

```env
EIA_API_KEY=
```

### Initial decision

Optional for phase one. Use BLS CPI energy components first.

---

# 6. European Union and Euro Area Providers

## 6.1 Eurostat API

### Official links

- https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access/api-introduction
- https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access
- https://ec.europa.eu/eurostat/web/query-builder
- https://ec.europa.eu/eurostat/data/web-services

### What it provides

- HICP and components
- HICP weights
- food and energy inflation
- PPI and import prices
- labour costs and wages
- house prices and rents
- GDP and national accounts
- household income and consumption
- EU, Euro Area, and country aggregates

### Indicators supported

- Headline Consumer Inflation
- Underlying Inflation
- Essential Cost Inflation
- Fixed-Lifestyle Inflation
- Housing Inflation
- Producer and Import Inflation
- Economy-Wide Inflation
- Purchasing-Power Squeeze
- Global Consumer Inflation
- Global Essential Inflation

### Authentication

- Registration: no
- API key: no
- Cost: free public access
- Status: available

### API options

Statistics API:

```text
https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/DATASET_CODE
```

Use SDMX 2.1/3.0 when metadata, dimensions, and reusable adapters matter.

### Rules

- Store raw responses because Eurostat generally exposes the latest revision.
- Distinguish EU from Euro Area.
- Preserve geo, unit, frequency, and adjustment codes.
- Filter large requests.
- Do not describe all European countries as EU or Euro Area members.

---

## 6.2 ECB Data Portal API

### Official links

- https://data.ecb.europa.eu/help/api/overview
- https://data.ecb.europa.eu/help/api/data
- https://data.ecb.europa.eu/help/api/metadata
- https://data-api.ecb.europa.eu/service/

### What it provides

- M1, M2, and M3
- Euro Area monetary aggregates
- bank lending and private-sector credit
- interest rates
- exchange rates
- financial institutions
- inflation expectations

### Indicators supported

- Broad Money Expansion
- Excess Money Growth
- Global Monetary Expansion
- Global Excess Money Growth
- monetary and credit context

### Authentication

- Registration: no
- API key: no
- Status: available

### Protocol

- SDMX 2.1 REST

### Rules

- Euro Area is not the same as the EU.
- Build keys from official data structures.
- Cache metadata and codelists.
- Avoid full-dataset requests.

---

# 7. Global Backbone Providers

## 7.1 World Bank Indicators API

### Official links

- https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
- https://datahelpdesk.worldbank.org/knowledgebase/articles/898581
- https://datahelpdesk.worldbank.org/knowledgebase/articles/898599

### What it provides

- population
- GDP and GDP PPP
- real GDP growth
- GDP deflator
- household consumption
- annual CPI inflation
- broad-money indicators
- country and region metadata
- global weights and coverage inputs

### Indicators supported

- Global Consumer Inflation weights
- Global Monetary Expansion weights
- Global Excess Money Growth
- Median Country Inflation
- country resolution and coverage

### Authentication

- Registration: no
- API key: no
- Status: available

### Endpoint

```text
https://api.worldbank.org/v2/country/{COUNTRY}/indicator/{INDICATOR}?format=json
```

### Rules

- Much data is annual.
- Handle pagination.
- Filter regions and income groups from country calculations.
- Store source database and metadata.
- Do not use annual World Bank CPI when current monthly official data exists.

---

## 7.2 BIS Statistics API

### Official links

- https://stats.bis.org/api-doc/v2/
- https://data.bis.org/
- https://data.bis.org/help/legal

### What it provides

- residential property prices
- real house prices
- private-sector credit
- global liquidity
- effective exchange rates
- debt-service ratios
- cross-border banking

### Indicators supported

- Housing Inflation
- Global Housing and Asset Inflation
- credit and global-liquidity context

### Authentication

- Registration: no
- API key: no
- Status: available

### Rules

- Many series are quarterly.
- Coverage varies.
- Read the data structure before constructing SDMX keys.
- Cache responses.
- Attribute BIS where required.
- Credit growth is not the same as broad-money growth.

---

## 7.3 IMF Data API

### Official links

- https://data.imf.org/en/Resource-Pages/IMF-API
- https://data.imf.org/datasets
- https://data.imf.org/

### What it provides

Potentially:

- CPI and supported components
- PPI
- monetary and financial statistics
- broad money
- exchange rates
- GDP and national accounts
- international liquidity
- WEO indicators
- global macroeconomic comparisons

### Indicators supported

- Global Consumer Inflation
- Median Country Inflation
- Global Monetary Expansion
- Global Excess Money Growth
- Global Producer Pressure
- Global Inflation Synchronization

### Authentication

- Selected endpoint: **no authentication required**
- Portal account: useful for Swagger exploration
- Status: available and tested by the project owner

Do not add an IMF secret to `.env` unless another endpoint explicitly requires one.

### Protocols

- SDMX 2.1
- SDMX 3.0

### Integration order

1. discover dataflows;
2. retrieve data structures;
3. retrieve codelists;
4. test small filtered requests;
5. map indicators;
6. validate coverage.

### Rules

- Do not assume old IFS codes map directly to the new portal.
- Store dataset ID, version, dimension order, and indicator code.
- Confirm whether values are indexes, levels, or growth rates.
- Avoid broad unfiltered requests.

---

## 7.4 ILOSTAT

### Official links

- https://ilostat.ilo.org/data/
- https://ilostat.ilo.org/about/get-started/
- https://ilostat.ilo.org/data/bulk/
- https://ilostat.ilo.org/resources/sdmx-tools/

### What it provides

- wages and earnings
- labour income
- minimum wages
- labour costs
- employment
- hours worked
- demographic and occupational breakdowns

### Indicators supported

- Purchasing-Power Squeeze
- global real wage analysis
- labour-market affordability context

### Authentication

- Public bulk download: no key
- Public SDMX access: no key documented for normal use
- Status: available

### Recommendation

Use bulk downloads for large multi-country pipelines and SDMX for targeted queries.

### Rules

- Preserve mean/median, hourly/monthly, nominal/real distinctions.
- Store sex, age, occupation, unit, frequency, and source.
- Do not silently combine survey and administrative data.

---

## 7.5 OECD Data Explorer API

### Official links

- https://www.oecd.org/en/data/insights/data-explainers/2024/09/api.html
- https://data-explorer.oecd.org/

### What it provides

- CPI and core inflation
- PPI
- GDP deflator
- house prices and rents
- wages and labour costs
- household income and consumption
- national accounts

### Indicators supported

Most country indicators for OECD members, especially:

- Underlying Inflation
- Housing Inflation
- Economy-Wide Inflation
- Purchasing-Power Squeeze

### Authentication

- Public statistical API: no API key normally required
- Status: available

### Rules

- Best coverage is for OECD countries and partners.
- Prefer national sources for country primary data.
- Use OECD as a standardized comparison/fallback.
- Cache data and respect fair-use limits.

---

## 7.6 FAOSTAT API

### Official links

- https://www.fao.org/faostat/en/
- https://www.fao.org/statistics/highlights-archive/highlights-detail/faostat-launches-a-new-api-developer-portal-to-make-data-access-easier/en

### What it provides

- agricultural producer prices
- food production
- commodity data
- food supply
- food balances
- agriculture-related inputs and outputs
- metadata and dimension codes

### Indicators supported

- Global Essential Inflation context
- essential food pressure
- Global Producer Pressure
- monetary-history and food-supply context

### Authentication

- Status: access token available
- Exact token placement: verify in the logged-in developer portal
- Quota: verify in the portal

Do not assume a header scheme. Follow the OpenAPI security definition.

Possible examples only:

```http
Authorization: Bearer TOKEN
```

or:

```http
X-API-Key: TOKEN
```

```env
FAOSTAT_ACCESS_TOKEN=
```

### Initial decision

Defer until Global Essential Inflation and Global Producer Pressure.

For the initial demo, use:

- BLS food CPI for the US
- Eurostat HICP food components for Europe

### Rules

- Producer prices are not retail consumer prices.
- Many series are annual.
- Do not replace national CPI with FAOSTAT.
- Store area, item, element, unit, domain, and year.
- Treat the token as a secret.

---

# 8. Thailand Expansion

## 8.1 TPSO Economic Index API

### Official links

- https://index.tpso.go.th/document/cpiu/get-month
- https://index.tpso.go.th/document/cpiu/post-month
- https://index.tpso.go.th/document/ppi/get-month
- https://index-api.tpso.go.th

### What it provides

- Thailand CPI
- CPI components and regions
- low-income indexes where available
- PPI
- import and export price indexes
- other economic indexes

### Indicators supported

- Headline Consumer Inflation
- Underlying Inflation
- Essential Cost Inflation
- Fixed-Lifestyle Inflation
- Producer and Import Inflation

### Authentication

- No API key shown in public documentation
- No documented registration requirement for the open endpoints
- Status: available

### Rules

- Handle Buddhist Era years.
- Store base year.
- Call master-data endpoints before using commodity codes.
- Preserve Thai/English labels.
- Do not merge indexes with different bases without linking.

---

## 8.2 Bank of Thailand API

### Official links

- https://portal.api.bot.or.th/
- https://portal.api.bot.or.th/manual
- https://portal.api.bot.or.th/portal/catalogue-products

### What it provides

- exchange rates
- interest rates
- money supply
- monetary statistics
- bank credit
- financial institutions
- external and real-sector statistics

### Indicators supported

- Broad Money Expansion
- Excess Money Growth
- exchange-rate pass-through
- Thailand financial conditions

### Authentication

- Registration: required
- Product subscription: required
- Application/token: required
- Header: `Authorization`
- Status: not yet available

```env
BOT_API_TOKEN=
```

### Initial decision

Not required for the US/EU demo. Add when Thailand becomes active scope.

---

# 9. Asset and Market Providers

## 9.1 CoinGecko

### Official links

- https://docs.coingecko.com/
- https://docs.coingecko.com/docs/setting-up-your-api-key

### What it provides

- Bitcoin and cryptocurrency prices
- historical prices
- local fiat currency quotes
- market capitalization and volume

### Indicators supported

- Global Housing and Asset Inflation
- Bitcoin versus CPI
- Bitcoin versus M2

### Authentication

Depends on public/demo/paid plan.

### Rules

- Crypto returns are asset-price changes, not consumer inflation.
- Store quote currency and time zone.
- Cache historical data.

---

## 9.2 Alpha Vantage

### Official links

- https://www.alphavantage.co/documentation/
- https://www.alphavantage.co/support/

### What it provides

- equities
- ETFs
- market indexes
- foreign exchange
- commodities

### Authentication

- API key required
- Status: available

```env
ALPHA_VANTAGE_API_KEY=
```

### Rules

- Cache results.
- Free quotas may be restrictive.
- Do not use as a core source when an official provider exists.
- Confirm adjusted versus unadjusted prices.

---

## 9.3 Nasdaq Data Link

### Official links

- https://docs.data.nasdaq.com/
- https://docs.data.nasdaq.com/docs/getting-started

### What it provides

Depending on dataset:

- market data
- commodities
- economic data
- alternative data

### Authentication

- Account required
- API key normally required
- Free and paid datasets exist
- Status: not available

### Initial decision

Defer. Existing providers already cover the MVP.

---

# 10. Provider-to-Indicator Matrix

## Country indicators

| Indicator | US primary | EU/Euro Area primary | Fallback |
|---|---|---|---|
| Headline Consumer Inflation | BLS | Eurostat | IMF, OECD, World Bank |
| Underlying Inflation | BLS | Eurostat | OECD, IMF |
| Essential Cost Inflation | BLS components | Eurostat components | IMF/OECD, FAOSTAT context |
| Fixed-Lifestyle Inflation | BLS category indexes | Eurostat components | custom basket |
| Housing Inflation | BLS/FRED/BIS | Eurostat/BIS | BIS, OECD |
| Broad Money Expansion | FRED | ECB | IMF |
| Excess Money Growth | FRED + BEA | ECB + Eurostat | IMF + World Bank |
| Producer and Import Inflation | BLS/EIA | Eurostat | IMF/OECD/FAOSTAT |
| Economy-Wide Inflation | BEA | Eurostat | IMF/World Bank/OECD |
| Purchasing-Power Squeeze | BLS + BEA | Eurostat | ILOSTAT/OECD |

## Global indicators

| Indicator | Recommended providers |
|---|---|
| Global Consumer Inflation | IMF CPI + World Bank PPP/consumption weights |
| Median Country Inflation | IMF or World Bank |
| Global Essential Inflation | IMF/OECD/Eurostat components + FAOSTAT context |
| Global Monetary Expansion | IMF + ECB/national overrides |
| Global Excess Money Growth | IMF money/GDP + World Bank fallback |
| Global Producer Pressure | IMF/OECD PPI + FAOSTAT + energy data |
| Global Housing and Asset Inflation | BIS + CoinGecko + optional market provider |
| Global Inflation Synchronization | IMF country data, calculated internally |

---

# 11. Authentication Summary

| Provider | Registration | Secret required | Status |
|---|---:|---:|---|
| BLS v1 | No | No | Available |
| BLS v2 | Yes | Registration key | CAPTCHA blocked |
| BEA | Yes | API key | Available |
| FRED | Yes | API key | Available |
| EIA | Yes | API key | Available |
| Eurostat | No | No | Available |
| ECB | No | No | Available |
| World Bank | No | No | Available |
| BIS | No | No | Available |
| IMF selected endpoint | No | No | Available and tested |
| ILOSTAT | No for public access | No | Available |
| OECD | No for public statistics | No | Available |
| FAOSTAT | Portal access exists | Access token | Auth scheme pending verification |
| TPSO | No documented requirement | No documented secret | Available |
| BOT | Yes | Authorization token | Not yet available |
| CoinGecko | Depends on plan | Depends on plan | Available |
| Alpha Vantage | Yes | API key | Available |
| Nasdaq Data Link | Yes | API key | Not yet available |

---

# 12. Environment Variables

```env
BEA_API_KEY=
FRED_API_KEY=
EIA_API_KEY=
FAOSTAT_ACCESS_TOKEN=
BOT_API_TOKEN=
COINGECKO_API_KEY=
ALPHA_VANTAGE_API_KEY=
NASDAQ_DATA_LINK_API_KEY=
```

No IMF credential is currently required.

## `.gitignore`

```gitignore
.env
.env.*
!.env.example
```

Never expose secrets to React or commit them to GitHub.

---

# 13. Source Registry

AI must not dynamically select production providers.

```yaml
USA:
  headline_consumer_inflation:
    primary:
      provider: bls
      series_id: CUUR0000SA0
    fallback:
      provider: imf
      dataset_id: CPI
    expected_frequency: monthly
    expected_unit: index

EA:
  headline_consumer_inflation:
    primary:
      provider: eurostat
      dataset: prc_hicp_midx
    fallback:
      provider: imf
      dataset_id: CPI

  broad_money_expansion:
    primary:
      provider: ecb
      dataflow: BSI
    fallback:
      provider: imf
      dataset_id: MFS
```

Store:

- provider
- dataset
- series ID
- frequency
- unit
- seasonal adjustment
- geography
- primary/fallback role
- validation status
- last review date

---

# 14. Normalized Provider Output

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
  "source_url": "https://www.bls.gov/",
  "is_estimated": false,
  "validation_status": "validated"
}
```

Provider-specific parsing must happen before the calculation engine.

---

# 15. Validation Rules

Validate every series for:

1. provider;
2. dataset/series ID;
3. geography;
4. frequency;
5. unit;
6. seasonal adjustment;
7. observation period;
8. duplicates;
9. missing periods;
10. suspicious values;
11. revisions;
12. schema changes.

Example:

```text
Expected: monthly CPI index
Received: annual percentage change
Action: reject and log schema mismatch
```

Never calculate an index formula from a growth-rate series.

---

# 16. Caching Policy

| Data type | Suggested check frequency |
|---|---|
| CPI/PPI | Daily around release dates |
| Money supply | Daily or weekly |
| GDP | Daily check; changes only on releases |
| Wages | Weekly |
| House prices | Weekly |
| Population/PPP | Monthly or quarterly |
| Asset prices | Daily for demo charts |
| Metadata/codelists | Weekly or monthly |

Rules:

- cache raw responses;
- cache normalized observations;
- store retrieval timestamps;
- use exponential backoff;
- respect HTTP 429;
- never retry malformed requests indefinitely.

---

# 17. Bias-Control Rules

- Select providers before viewing results.
- Do not switch providers to obtain a preferred number.
- Version-control source mappings.
- Display methodology differences.
- Preserve missing values instead of inventing them.
- Keep AI outside deterministic calculations.
- Log every fallback.
- Mark official, fallback, estimated, stale, and partial values.

---

# 18. Implementation Sequence

## Phase 1 — US/EU demo

1. World Bank metadata
2. BLS v1
3. BEA
4. FRED
5. Eurostat
6. ECB
7. BIS
8. normalized schema
9. calculation engine
10. methodology/source display

## Phase 2 — Global macro

1. IMF SDMX
2. global weights
3. coverage reporting
4. global CPI
5. global monetary aggregates
6. synchronization

## Phase 3 — Labour and essentials

1. ILOSTAT
2. OECD
3. FAOSTAT authentication verification
4. food/agriculture pipeline
5. purchasing-power analysis

## Phase 4 — Thailand

1. TPSO
2. BOT registration/token
3. Thailand source registry

## Phase 5 — Optional assets

1. CoinGecko
2. Alpha Vantage
3. Nasdaq only if a confirmed gap remains

---

# 19. MVP Decision

The first demo does not require:

- BLS v2
- BOT
- FAOSTAT
- Nasdaq Data Link

It can be built with:

```text
BLS v1
BEA
FRED
Eurostat
ECB
World Bank
BIS
```

IMF should be the next major integration for the global dashboard. The selected IMF endpoint has been verified to work without authentication.

---

# 20. Traceability Rule

Every displayed number must remain traceable through:

```text
Displayed value
→ calculation version
→ normalized observations
→ provider response
→ source series
→ official documentation
```

If any link is missing, the number must not be labeled validated.
