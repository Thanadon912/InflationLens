---
title: Global Inflation Methodology
document_id: global-inflation-methodology
version: 1.0.2
status: approved
language: en
scope: global
indicator_count: 8
---

# Global Inflation Methodology

## 1. Purpose

This document defines a transparent methodology for measuring inflation at the global level.

There is no single globally observed consumer basket. Global inflation must therefore be constructed by combining country-level observations using explicit aggregation rules.

The methodology uses eight global lenses:

1. Global Consumer Inflation
2. Median Country Inflation
3. Global Essential Inflation
4. Global Monetary Expansion
5. Global Excess Money Growth
6. Global Producer Pressure
7. Global Housing and Asset Inflation
8. Global Inflation Synchronization

The system must preserve the distinction between:

- consumer-price inflation;
- monetary expansion;
- producer-cost pressure;
- housing and asset inflation;
- cross-country synchronization.

These values must not be merged into one official-looking number without clear labeling.

---

# 2. Global Methodology Principles

## 2.1 Calculate locally before aggregating globally

Where possible, calculate each country's growth rate in its own currency and according to its local statistical definition.

Do not first convert all national price indexes or money stocks into U.S. dollars unless exchange-rate exposure is the subject of the indicator.

Preferred sequence:

1. obtain national series;
2. calculate national growth;
3. validate national metadata;
4. assign aggregation weight;
5. aggregate across countries.

## 2.2 Do not treat countries as perfectly comparable

Country indicators may differ in:

- basket composition;
- housing treatment;
- monetary aggregate definition;
- index base;
- publication frequency;
- quality adjustment;
- seasonal adjustment;
- informal-economy coverage.

Global aggregation reduces these differences into a summary statistic but does not eliminate them.

## 2.3 Use multiple weighting systems

No global weighting system is neutral.

Recommended weighting options:

- household-consumption PPP weights;
- GDP PPP weights;
- population weights;
- market-exchange-rate weights;
- equal-country weights.

The default weighting method must be explicit.

## 2.4 Separate level aggregation from growth aggregation

If national price indexes use unrelated base years, do not average index levels directly.

Preferred approach:

- aggregate national price relatives or inflation rates;
- chain the global index over time.

## 2.5 Prevent silent survivorship bias

A global result must report:

- number of included countries;
- population coverage;
- GDP coverage;
- consumption coverage;
- missing-country list;
- whether weights were renormalized.

## 2.6 AI must not generate global data

AI may help map country names, source terminology, and series identifiers.

AI must not:

- invent country observations;
- fill missing values without a documented model;
- change country weights;
- exclude countries because they create an inconvenient result;
- choose a weighting method after seeing the answer.

---

# 3. Shared Global Mathematical Conventions

## 3.1 Country inflation rate

For country \(c\):

\[
\pi_{c,t}
=
\left(
\frac{P_{c,t}}{P_{c,t-k}}-1
\right)\times100
\]

where \(k\) is 12 for monthly year-over-year data or 4 for quarterly year-over-year data.

## 3.2 Arithmetic weighted average

\[
\pi^{G}_t
=
\sum_{c=1}^{C}
w_{c,t}\pi_{c,t}
\]

subject to:

\[
w_{c,t}\ge0
\qquad \text{and} \qquad
\sum_{c=1}^{C}w_{c,t}=1
\]

## 3.3 Geometric aggregation of price relatives

Let:

\[
R_{c,t}
=
\frac{P_{c,t}}{P_{c,t-1}}
\]

Then:

\[
R^{G}_t
=
\prod_{c=1}^{C}
R_{c,t}^{w_{c,t}}
\]

Global period inflation:

\[
\pi^{G}_t
=
(R^{G}_t-1)\times100
\]

## 3.4 Chain-linked global index

Set:

\[
GPI_0=100
\]

Then:

\[
GPI_t
=
GPI_{t-1}R^{G}_t
\]

Year-over-year global inflation:

\[
\pi^{G,YoY}_t
=
\left(
\frac{GPI_t}{GPI_{t-12}}-1
\right)\times100
\]

## 3.5 Renormalization for missing countries

If available countries for a given sub-indicator form set \(A_t\):

\[
w^{*}_{c,t}
=
\frac{
w_{c,t}
}{
\sum_{j\in A_t}w_{j,t}
}
\]

This renormalization rule applies uniformly to **both primary and secondary/optional weight mappings** (including `gdp_ppp_weights`, `consumption_ppp_weights`, `population_weights`, `import_share_weights`, `housing_weights`, `commodity_weights`, and `country_weights`). Each sub-calculation must intersect its value mapping with its corresponding weight mapping and renormalize over \(A_t\) whenever coverage exceeds the documented threshold and missing countries are not structurally dominant.

## 3.6 Recommended coverage thresholds

Suggested minimums:

- 85% of global household consumption for consumer indicators;
- 85% of global GDP PPP for macro indicators;
- 80% of global population for population-weighted indicators.

Results below thresholds should be labeled partial.

## 3.7 Outlier rule

Do not remove hyperinflation or deflation observations merely because they are extreme.

Instead:

- retain them in weighted means;
- use median and trimmed views as robustness measures;
- flag suspected data errors separately.

---

# 4. Weighting Systems

## 4.1 Household-consumption PPP weight

\[
w^{consPPP}_{c,t}
=
\frac{
Consumption^{PPP}_{c,t}
}{
\sum_jConsumption^{PPP}_{j,t}
}
\]

Recommended default for global consumer inflation.

## 4.2 GDP PPP weight

\[
w^{GDPppp}_{c,t}
=
\frac{
GDP^{PPP}_{c,t}
}{
\sum_jGDP^{PPP}_{j,t}
}
\]

Recommended for economy-wide or monetary indicators.

## 4.3 Population weight

\[
w^{pop}_{c,t}
=
\frac{
Population_{c,t}
}{
\sum_jPopulation_{j,t}
}
\]

Useful for the inflation environment experienced by the average person across countries, but it does not adjust for consumption volume.

## 4.4 Equal-country weight

\[
w^{equal}_{c,t}
=
\frac{1}{C_t}
\]

Useful for describing the typical country.

## 4.5 Market-exchange-rate weight

\[
w^{MER}_{c,t}
=
\frac{
GDP^{USD}_{c,t}
}{
\sum_jGDP^{USD}_{j,t}
}
\]

Useful for global financial-market analysis, but sensitive to exchange-rate movements.

## 4.6 Weight update rule

Weights should be updated annually where possible.

To reduce look-ahead bias, use lagged weights:

\[
w_{c,t}=w_{c,t-1}^{annual}
\]

Document whether weights are current, lagged, fixed-base, or interpolated.

---

# 5. Indicator 1 — Global Consumer Inflation

## 5.1 Question answered

How quickly are consumer prices rising across the global household-consumption system?

## 5.2 Preferred default

Use country headline CPI rates aggregated with household-consumption PPP weights.

## 5.3 Arithmetic formulation

\[
\pi^{GCI}_t
=
\sum_c
w^{consPPP}_{c,t-1}
\pi^{headline}_{c,t}
\]

## 5.4 Geometric chained formulation

Country monthly price relative:

\[
R_{c,t}
=
\frac{CPI_{c,t}}{CPI_{c,t-1}}
\]

Global price relative:

\[
R^{GCI}_t
=
\prod_c
R_{c,t}^{w^{consPPP}_{c,t-1}}
\]

Global index:

\[
GCI_t
=
GCI_{t-1}R^{GCI}_t
\]

Year-over-year inflation:

\[
\pi^{GCI,YoY}_t
=
\left(
\frac{GCI_t}{GCI_{t-12}}-1
\right)\times100
\]

## 5.5 Required inputs

- country CPI indexes or rates;
- country consumption PPP values;
- country coverage;
- national CPI metadata;
- common monthly or quarterly calendar.

## 5.6 Interpretation

Global Consumer Inflation is the closest dashboard measure to worldwide consumer-price inflation.

It is not a literal global household basket because each country's CPI basket remains local.

## 5.7 Alternative views

Display optional comparisons using:

- GDP PPP weights;
- population weights;
- market-exchange-rate weights.

Differences between these views are economically meaningful and should not be hidden.

---

# 6. Indicator 2 — Median Country Inflation

## 6.1 Question answered

What inflation rate is experienced by the country in the middle of the global distribution?

## 6.2 Unweighted median

Order country inflation rates:

\[
\pi_{(1),t}
\le
\pi_{(2),t}
\le
\cdots
\le
\pi_{(C),t}
\]

For odd \(C\):

\[
Median_t
=
\pi_{\left(\frac{C+1}{2}\right),t}
\]

For even \(C\):

\[
Median_t
=
\frac{
\pi_{\left(\frac{C}{2}\right),t}
+
\pi_{\left(\frac{C}{2}+1\right),t}
}{2}
\]

## 6.3 Weighted median

A population- or consumption-weighted median may also be calculated.

Find country \(m\) such that:

\[
\sum_{c<m}w_{(c),t}<0.5
\]

and:

\[
\sum_{c\le m}w_{(c),t}\ge0.5
\]

Then:

\[
Median^{weighted}_t
=
\pi_{(m),t}
\]

## 6.4 Interpretation

Median Country Inflation is resistant to very large economies and extreme inflation outliers.

It answers "What is happening in the typical country?" rather than "What is happening in the average unit of global consumption?"

## 6.5 Required display

Show:

- median;
- 25th percentile;
- 75th percentile;
- minimum;
- maximum;
- country count;
- optional weighted median.

---

# 7. Indicator 3 — Global Essential Inflation

## 7.1 Question answered

How quickly are globally essential household costs rising?

## 7.2 Country-level prerequisite

Each country should first calculate:

\[
\pi^{essential}_{c,t}
=
\sum_{i\in E_c}
w^{essential}_{i,c}
\pi_{i,c,t}
\]

The category map should use a common global taxonomy while preserving local subcomponents.

## 7.3 Global aggregation

\[
\pi^{GEI}_t
=
\sum_c
w^{consPPP}_{c,t-1}
\pi^{essential}_{c,t}
\]

## 7.4 Alternative population-weighted form

\[
\pi^{GEI,pop}_t
=
\sum_c
w^{pop}_{c,t-1}
\pi^{essential}_{c,t}
\]

## 7.5 Standardized essential categories

Recommended top-level categories:

- basic food;
- shelter;
- household energy;
- essential transport;
- healthcare;
- water;
- basic education;
- communications.

## 7.6 Cross-country category normalization

A mapping table should associate local CPI categories with the global taxonomy.

Example:

```json
{
  "country": "THA",
  "local_series": "Food and non-alcoholic beverages",
  "global_category": "basic_food",
  "mapping_confidence": "high"
}
```

## 7.7 Interpretation

Global Essential Inflation is designed to reveal cost pressure that may be understated by broad consumer baskets.

It is not a poverty index unless weights specifically represent low-income households.

## 7.8 Limitations

- public provision differs across countries;
- climate affects energy needs;
- transport requirements differ;
- informal prices may be underrepresented;
- category granularity varies.

---

# 8. Indicator 4 — Global Monetary Expansion

## 8.1 Question answered

How quickly are broad money aggregates expanding across the global financial system?

## 8.2 Country-level calculation

For each country:

\[
g^{money}_{c,t}
=
\left(
\frac{M_{c,t}}{M_{c,t-12}}-1
\right)\times100
\]

Use local-currency monetary aggregates.

## 8.3 Global weighted aggregation

Preferred GDP PPP form:

\[
GME_t
=
\sum_c
w^{GDPppp}_{c,t-1}
g^{money}_{c,t}
\]

Alternative consumption PPP form:

\[
GME^{cons}_t
=
\sum_c
w^{consPPP}_{c,t-1}
g^{money}_{c,t}
\]

## 8.4 Geometric growth aggregation

\[
1+GME^{geo}_t
=
\prod_c
\left(
1+g^{money}_{c,t}
\right)^{w_c}
\]

Rates must be expressed as decimals inside the formula.

## 8.5 Why not sum money stocks in U.S. dollars by default?

A direct conversion:

\[
GlobalMoney^{USD}_t
=
\sum_c
M_{c,t}E^{USD}_{c,t}
\]

mixes two effects:

- domestic money creation;
- exchange-rate movements.

This may be useful for dollar-liquidity analysis but should not be the default monetary-expansion measure.

## 8.6 Required metadata

Store each country's:

- monetary aggregate name;
- institutional coverage;
- included deposit types;
- currency denomination;
- seasonal adjustment;
- break history;
- publication lag.

## 8.7 Interpretation

Global Monetary Expansion is a liquidity and monetary-quantity indicator.

It must not be labeled as global consumer inflation.

---

# 9. Indicator 5 — Global Excess Money Growth

## 9.1 Question answered

Is global broad money expanding faster than global real output?

## 9.2 Aggregate-first approach

\[
GEMG_t
=
GME_t-g^{realGDP,G}_t
\]

where \(GME_t\) is Global Monetary Expansion and \(g^{realGDP,G}_t\) is global real GDP growth under a consistent weighting system.

## 9.3 Country-first approach

\[
EMG_{c,t}
=
g^{money}_{c,t}-g^{realGDP}_{c,t}
\]

Let \(A_t\) be the set of countries with both \(g^{money}_{c,t}\), \(g^{realGDP}_{c,t}\), and weight \(w_c\). Using renormalized weights \(w^*_c = w_c / \sum_{j \in A_t} w_j\):

\[
GEMG_t
=
\sum_{c \in A_t}w^*_cEMG_{c,t}
\]

## 9.4 Velocity-adjusted formulation

For country \(c\):

\[
V_{c,t}
=
\frac{
NominalGDP_{c,t}
}{
M_{c,t}
}
\]

Then:

\[
MP_{c,t}
=
g(M_{c,t})+g(V_{c,t})-g(Y_{c,t})
\]

Global aggregation over the available country set \(A^{MP}_t\) with renormalized weights \(w^*_c\):

\[
GMP_t
=
\sum_{c \in A^{MP}_t}w^*_cMP_{c,t}
\]

## 9.5 Interpretation

Global Excess Money Growth is a monetary-pressure indicator.

A positive value suggests money is expanding faster than real production, but price outcomes depend on:

- velocity;
- money demand;
- financial intermediation;
- capital flows;
- asset-market allocation;
- exchange rates;
- supply constraints.

## 9.6 Consistency rule

Use the same weighting basis for money growth and real GDP growth wherever possible.

Do not subtract a GDP-PPP-weighted output measure from a market-exchange-rate-weighted money measure without a warning.

---

# 10. Indicator 6 — Global Producer Pressure

## 10.1 Question answered

How strong are upstream inflation pressures across producers, trade, commodities, energy, and logistics?

## 10.2 Country producer-price component

\[
GPP^{ppi}_t
=
\sum_c
w^{GDPppp}_{c,t-1}
\pi^{ppi}_{c,t}
\]

## 10.3 Global import-price component

\[
GPP^{import}_t
=
\sum_c
w^{importshare}_{c,t-1}
\pi^{import}_{c,t}
\]

where:

\[
w^{importshare}_{c,t}
=
\frac{
Imports_{c,t}
}{
\sum_jImports_{j,t}
}
\]

## 10.4 Commodity component

Let commodity groups be indexed by \(k\):

\[
CommodityPressure_t
=
\sum_k
w^{commodity}_k
\pi^{commodity}_{k,t}
\]

## 10.5 Shipping or logistics component

\[
LogisticsPressure_t
=
\left(
\frac{
FreightIndex_t
}{
FreightIndex_{t-12}
}
-1
\right)\times100
\]

## 10.6 Composite producer-pressure score

Because components may use different scales and volatility, standardize them:

\[
z_{j,t}
=
\frac{
x_{j,t}-\mu_j
}{
\sigma_j
}
\]

Then:

\[
GPPS_t
=
\sum_j a_jz_{j,t}
\]

with:

\[
\sum_ja_j=1
\]

This is a pressure score, not an inflation rate.

## 10.7 Interpretation

Global Producer Pressure may lead consumer inflation, but pass-through is not automatic.

It may instead appear through:

- lower margins;
- reduced output;
- delayed investment;
- inventory changes;
- fiscal subsidies;
- supply-chain substitution.

---

# 11. Indicator 7 — Global Housing and Asset Inflation

## 11.1 Question answered

How quickly are major stores of wealth and access-to-ownership costs rising globally?

## 11.2 Required separation

Housing and financial assets must not be merged into consumer inflation.

Recommended sub-indicators:

- global rent inflation;
- global house-price inflation;
- global equity-price inflation;
- global bond-price or yield conditions;
- gold-price inflation;
- Bitcoin-price inflation.

## 11.3 Global house-price inflation

Country house-price growth:

\[
\pi^{house}_{c,t}
=
\left(
\frac{
HPI_{c,t}
}{
HPI_{c,t-4}
}
-1
\right)\times100
\]

Global aggregation:

\[
\pi^{house,G}_t
=
\sum_c
w^{housing}_{c,t-1}
\pi^{house}_{c,t}
\]

Possible weights:

- housing-market value;
- GDP PPP;
- population;
- number of households.

## 11.4 Global rent inflation

\[
\pi^{rent,G}_t
=
\sum_c
w^{consPPP}_{c,t-1}
\pi^{rent}_{c,t}
\]

## 11.5 Global equity inflation

For a global equity total-return or price index \(EQ_t\):

\[
\pi^{equity}_t
=
\left(
\frac{EQ_t}{EQ_{t-12}}-1
\right)\times100
\]

## 11.6 Gold and Bitcoin in multiple currencies

To avoid presenting only a U.S.-dollar perspective, calculate:

\[
Return^{asset}_{c,t}
=
\left(
\frac{
Price^{local}_{asset,c,t}
}{
Price^{local}_{asset,c,t-12}
}
-1
\right)\times100
\]

Then aggregate across currencies if desired.

## 11.7 Asset-to-income pressure

\[
AssetIncomeRatio_t
=
\frac{
AssetPriceIndex_t
}{
IncomeIndex_t
}
\]

Growth:

\[
g(AssetIncomeRatio_t)
\approx
g(AssetPriceIndex_t)-g(IncomeIndex_t)
\]

## 11.8 Interpretation

This indicator measures changes in access to assets and stores of value.

It is relevant to monetary history and wealth inequality, but asset-price increases may also reflect:

- expected future cash flows;
- productivity;
- interest-rate changes;
- risk premia;
- scarcity;
- speculation.

Do not attribute all asset inflation to money growth.

---

# 12. Indicator 8 — Global Inflation Synchronization

## 12.1 Question answered

How widespread and globally coordinated is inflation?

## 12.2 Share of countries above threshold

For threshold \(\tau\):

\[
ShareAbove_{\tau,t}
=
\frac{
\sum_c
\mathbf{1}
(
\pi_{c,t}>\tau
)
}{
C_t
}
\times100
\]

Population-weighted form:

\[
ShareAbove^{pop}_{\tau,t}
=
\sum_c
w^{pop}_{c,t}
\mathbf{1}
(
\pi_{c,t}>\tau
)
\times100
\]

## 12.3 Share of countries with accelerating inflation

\[
ShareAccelerating_t
=
\frac{
\sum_c
\mathbf{1}
(
\pi_{c,t}>\pi_{c,t-1}
)
}{
C_t
}
\times100
\]

## 12.4 Cross-country dispersion

Mean:

\[
\bar{\pi}_t
=
\frac{1}{C_t}
\sum_c\pi_{c,t}
\]

Standard deviation:

\[
Dispersion_t
=
\sqrt{
\frac{
\sum_c
(\pi_{c,t}-\bar{\pi}_t)^2
}{
C_t-1
}
}
\]

## 12.5 Interquartile range

\[
IQR_t
=
Q_{0.75,t}-Q_{0.25,t}
\]

## 12.6 Common-factor model

\[
\pi_{c,t}
=
\lambda_cF_t
+
\gamma_cR_{r(c),t}
+
\varepsilon_{c,t}
\]

where:

- \(F_t\) is a global inflation factor;
- \(R_{r(c),t}\) is a regional factor;
- \(\varepsilon_{c,t}\) is country-specific inflation.

## 12.7 Synchronization score

To combine diffusion shares (`[0, 100]%`) with cross-country dispersion (`percent_yoy`) without scale distortion, every component of the Synchronization Score must first be expressed as a dimensionless standard-deviation score (`standard_deviation_score`):

- For bounded diffusion shares \(S_t \in [0, 100]\) (\(ShareAccelerating_t\) and \(ShareAbove_{\tau,t}\)), standardize relative to the neutral \(50\%\) diffusion midpoint with scale \(\sigma_S = 25.0\) percentage points (mapping \([0\%, 100\%] \mapsto [-2\sigma, +2\sigma]\)), or against an empirical historical window \((\mu_S, \sigma_S)\) if provided:

\[
z(S_t)
=
\frac{S_t - 50}{25}
\]

- For cross-country dispersion \(Dispersion_t\), standardize against its historical window \((\mu_D, \sigma_D)\):

\[
z(Dispersion_t)
=
\frac{Dispersion_t - \mu_D}{\sigma_D}
\]

Then the composite Synchronization Score is:

\[
Sync_t
=
a\cdot z(ShareAccelerating_t)
+
b\cdot z(ShareAbove_{\tau,t})
-
c\cdot z(Dispersion_t),
\qquad
a+b+c=1
\]

Higher cross-country dispersion indicates divergence rather than synchronization and is therefore subtracted. This composite must be labeled a score (`standard_deviation_score`), not an inflation rate.

## 12.8 Interpretation

High synchronization suggests a common global force such as:

- commodity shock;
- global demand surge;
- monetary easing across many economies;
- supply-chain disruption;
- geopolitical shock.

Low synchronization suggests inflation is more country-specific.

---

# 13. Frequency Alignment

## 13.1 Preferred global frequency

Monthly for:

- CPI;
- broad money;
- PPI;
- commodity prices;
- asset prices.

Quarterly for:

- GDP;
- house prices in many countries;
- wage or income data in some countries.

## 13.2 Mixed-frequency rule

Do not treat stale quarterly values as current monthly observations without labeling them.

Recommended options:

- show each indicator at native frequency;
- use trailing-twelve-month values;
- use mixed-frequency models only as an optional estimated layer;
- preserve official observations separately.

## 13.3 Release-lag rule

The global dashboard date should not imply that every component is equally current.

Store:

- observation period;
- release date;
- age in days;
- stale-data flag.

---

# 14. Country Coverage and Bias

## 14.1 Coverage report

Each global indicator must publish:

\[
PopulationCoverage_t
=
\frac{
\sum_{c\in A_t}Population_{c,t}
}{
\sum_cPopulation_{c,t}
}
\times100
\]

\[
GDPCoverage_t
=
\frac{
\sum_{c\in A_t}GDP^{PPP}_{c,t}
}{
\sum_cGDP^{PPP}_{c,t}
}
\times100
\]

\[
ConsumptionCoverage_t
=
\frac{
\sum_{c\in A_t}Consumption^{PPP}_{c,t}
}{
\sum_cConsumption^{PPP}_{c,t}
}
\times100
\]

## 14.2 Emerging-market bias

Do not rely only on countries with easy APIs. This can overrepresent advanced economies.

## 14.3 Hyperinflation treatment

Hyperinflation countries must remain visible.

Recommended display:

- weighted mean;
- median;
- 90th percentile;
- list of extreme cases.

## 14.4 Informal-economy limitation

Official price collection may underrepresent informal markets. This limitation should be documented where material.

---

# 15. Optional Global Dashboard Structure

## 15.1 Consumer Pressure

- Global Consumer Inflation
- Median Country Inflation
- Global Essential Inflation

## 15.2 Monetary Pressure

- Global Monetary Expansion
- Global Excess Money Growth

## 15.3 Upstream Pressure

- Global Producer Pressure

## 15.4 Wealth and Breadth

- Global Housing and Asset Inflation
- Global Inflation Synchronization

This grouping is explanatory. It does not imply that all values share the same unit.

---

# 16. Optional Global Composite Score

A global composite is allowed only as an analytical score.

## 16.1 Standardization

\[
z_{i,t}
=
\frac{
x_{i,t}-\mu_i
}{
\sigma_i
}
\]

## 16.2 Composite

\[
GlobalPressureScore_t
=
\sum_iw_iz_{i,t}
\]

subject to:

\[
\sum_iw_i=1
\]

## 16.3 Prohibited label

Do not call this "Global True Inflation."

Recommended labels:

- Global Inflation Pressure Score;
- Global Monetary and Cost Pressure Score;
- Global Inflation Conditions Index.

## 16.4 Required disclosures

- components;
- weights;
- historical window;
- missing-data policy;
- standardization method;
- current coverage;
- methodology version.

---

# 17. Suggested Data Contract

```json
{
  "indicator_id": "global_consumer_inflation",
  "value": 4.2,
  "unit": "percent_yoy",
  "period": "2026-06",
  "aggregation_method": "geometric_chain",
  "weight_method": "household_consumption_ppp_lagged",
  "included_countries": 142,
  "population_coverage": 96.8,
  "gdp_ppp_coverage": 97.5,
  "consumption_ppp_coverage": 95.9,
  "publication_date": "2026-08-01",
  "methodology_version": "1.0.0",
  "confidence": "high",
  "is_estimated": false
}
```

---

# 18. AI Search and Source-Mapping Guidelines

## 18.1 AI responsibilities

AI may:

- resolve country names;
- translate indicator terminology;
- identify likely official institutions;
- propose source-series mappings;
- summarize national methodology;
- detect possible series breaks.

## 18.2 Deterministic responsibilities

Code must:

- retrieve data;
- parse values;
- validate frequency;
- calculate growth;
- apply weights;
- calculate coverage;
- generate global aggregates;
- record methodology version.

## 18.3 Verification rule

An AI-discovered series is not trusted until its metadata is validated.

Validation should include:

- source institution;
- series title;
- unit;
- frequency;
- seasonal-adjustment status;
- start date;
- last observation;
- revision policy;
- definition.

---

# 19. Revisions and Historical Integrity

## 19.1 Vintage data

Where possible, store the publication vintage.

A historical backtest should distinguish between:

- values known at the time;
- latest revised values.

## 19.2 Weight revisions

Rebuilding history with new weights may change past aggregates.

Store both:

- original-vintage index;
- latest-methodology reconstructed index.

## 19.3 Series breaks

Do not splice incompatible series silently.

Every splice must record:

- old series;
- new series;
- splice date;
- linking method;
- reason;
- confidence.

---

# 20. Final Implementation Rule

A global inflation dashboard must reveal both the result and the construction of the result.

Every global value should answer:

1. Which countries were included?
2. What national indicator was used?
3. How were countries weighted?
4. How much of the world was covered?
5. What does the indicator capture?
6. What does it miss?
