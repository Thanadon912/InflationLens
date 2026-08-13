---
title: Country Inflation Methodology
document_id: country-inflation-methodology
version: 1.0.0
status: draft
language: en
scope: country
indicator_count: 10
---

# Country Inflation Methodology

## 1. Purpose

This document defines a transparent, reproducible, and country-level inflation methodology for a portfolio project.

The system does **not** claim that one number represents "true inflation." Instead, it measures inflation through ten separate lenses. Each lens answers a different question and exposes a different part of the inflation process.

The methodology is intentionally stored outside application code so that:

- formulas can be reviewed independently;
- data choices remain visible;
- AI cannot silently alter calculations;
- methodology changes can be versioned;
- the frontend can explain every displayed value;
- the project does not confuse interpretation with computation.

The ten country-level lenses are:

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

---

# 2. Core Methodology Principles

## 2.1 No single "true inflation" value

Inflation affects households, producers, workers, asset holders, renters, homeowners, and governments differently. A single index cannot represent all of these experiences without hiding important information.

The default output should therefore be a dashboard, not one master inflation rate.

## 2.2 Separate measurement from interpretation

The calculation engine must be deterministic.

AI may:

- identify country-specific terminology;
- map local indicator names to the common schema;
- explain methodology;
- help discover official data sources;
- summarize differences between indicators.

AI must not:

- invent missing observations;
- estimate undocumented weights;
- change formulas dynamically;
- choose a preferred result because it "looks realistic";
- replace official data without explicit labeling;
- convert a qualitative statement into a numeric value.

## 2.3 Preserve local methodology

Country data is not perfectly standardized. A country's CPI, broad money, housing data, or wage series may follow definitions that differ from those used elsewhere.

The system should preserve the official local definition and expose the differences in metadata rather than forcing false comparability.

## 2.4 Prefer transparent incompleteness over hidden estimation

If an input is missing, the system should display:

- unavailable;
- partial coverage;
- estimated;
- stale;
- low confidence.

It should not silently substitute another series.

## 2.5 Always display source and period

Every indicator must include:

- country code;
- value;
- unit;
- observation period;
- publication date;
- source institution;
- source series identifier;
- update frequency;
- seasonal-adjustment status;
- methodology version;
- data quality flag.

---

# 3. Shared Mathematical Conventions

## 3.1 Year-over-year growth

For an index or level \(X_t\):

\[
g^{YoY}_t(X)
=
\left(
\frac{X_t}{X_{t-12}}-1
\right)\times 100
\]

Use this for monthly series when comparing with the same month one year earlier.

## 3.2 Month-over-month growth

\[
g^{MoM}_t(X)
=
\left(
\frac{X_t}{X_{t-1}}-1
\right)\times 100
\]

## 3.3 Annualized monthly growth

\[
g^{Ann}_t(X)
=
\left[
\left(
\frac{X_t}{X_{t-1}}
\right)^{12}-1
\right]\times 100
\]

This is useful for detecting recent momentum, but it is more volatile than year-over-year inflation.

## 3.4 Quarterly annualized growth

\[
g^{QAnn}_t(X)
=
\left[
\left(
\frac{X_t}{X_{t-1}}
\right)^4-1
\right]\times 100
\]

Use when the source frequency is quarterly.

## 3.5 Weighted arithmetic aggregation

\[
A_t=\sum_{i=1}^{n} w_i x_{i,t}
\]

subject to:

\[
w_i \ge 0
\qquad \text{and} \qquad
\sum_{i=1}^{n}w_i=1
\]

## 3.6 Weighted geometric aggregation

For price relatives:

\[
G_t
=
\prod_{i=1}^{n}
\left(
\frac{P_{i,t}}{P_{i,0}}
\right)^{w_i}
\]

This is appropriate when proportional price changes matter more than absolute changes.

## 3.7 Log-change approximation

\[
\Delta \ln(X_t)
=
\ln(X_t)-\ln(X_{t-k})
\]

For small changes:

\[
100\Delta\ln(X_t)
\approx
g_t(X)
\]

## 3.8 Missing-value rule

When a component is unavailable, weights may be renormalized only if:

1. the missing component is not structurally dominant;
2. remaining coverage exceeds a documented threshold;
3. the result is labeled "partial coverage";
4. original and adjusted weights are stored.

Renormalized weight:

\[
w_i^{*}
=
\frac{w_i}{\sum_{j \in A}w_j}
\]

where \(A\) is the set of available components.

---

# 4. Indicator 1 — Headline Consumer Inflation

## 4.1 Question answered

How much has the average price of the official household consumption basket changed?

## 4.2 Preferred source

Use the official national CPI, HICP, or equivalent all-items consumer price index.

## 4.3 Primary formula

\[
\pi^{headline}_t
=
\left(
\frac{CPI_t}{CPI_{t-12}}-1
\right)\times100
\]

## 4.4 Secondary views

Month-over-month:

\[
\pi^{headline,MoM}_t
=
\left(
\frac{CPI_t}{CPI_{t-1}}-1
\right)\times100
\]

Three-month annualized momentum:

\[
\pi^{headline,3mAnn}_t
=
\left[
\left(
\frac{CPI_t}{CPI_{t-3}}
\right)^4-1
\right]\times100
\]

## 4.5 Required inputs

- all-items CPI index;
- index frequency;
- seasonal-adjustment status;
- reference base;
- official release date.

## 4.6 Interpretation

Headline CPI is the baseline consumer-price measure. It is necessary because it is official, widely understood, and historically available.

It is not sufficient because:

- it represents an average household;
- its weights may not match a specific household;
- housing treatment differs by country;
- substitutions may affect weights;
- asset prices are usually excluded;
- quality adjustments may reduce measured inflation;
- taxes, subsidies, and administered prices may distort comparisons.

## 4.7 Display guidance

Display:

- YoY rate;
- recent momentum;
- official source;
- basket update frequency;
- whether housing ownership costs are included.

Never label headline CPI as "actual inflation" or "true inflation."

---

# 5. Indicator 2 — Underlying Inflation

## 5.1 Question answered

How broad and persistent is inflation after reducing the influence of extreme or temporary price movements?

## 5.2 Preferred hierarchy

Use the best available official measure in this order:

1. weighted median inflation;
2. trimmed mean inflation;
3. model-based common inflation;
4. core CPI excluding defined volatile components.

The chosen method must be recorded.

## 5.3 Weighted median formula

Let component inflation rates be ordered:

\[
\pi_{(1),t}
\le
\pi_{(2),t}
\le
\cdots
\le
\pi_{(n),t}
\]

with expenditure weights \(w_{(i)}\).

The weighted median is the component \(m\) satisfying:

\[
\sum_{i<m} w_{(i)} < 0.5
\]

and:

\[
\sum_{i\le m} w_{(i)} \ge 0.5
\]

Then:

\[
\pi^{median}_t=\pi_{(m),t}
\]

## 5.4 Trimmed mean formula

Let lower and upper trim shares be \(\alpha\) and \(\beta\).

After sorting component inflation rates, remove observations representing cumulative weights below \(\alpha\) and above \(1-\beta\).

Then:

\[
\pi^{trim}_t
=
\frac{
\sum_{i \in R} w_i\pi_{i,t}
}{
\sum_{i \in R} w_i
}
\]

where \(R\) is the retained set.

## 5.5 Core exclusion formula

\[
\pi^{core}_t
=
\sum_{i \notin E} w_i^{*}\pi_{i,t}
\]

where \(E\) is the excluded set and:

\[
w_i^{*}
=
\frac{w_i}{\sum_{j \notin E}w_j}
\]

## 5.6 Model-based factor form

\[
\pi_{i,t}
=
\lambda_i F_t+\varepsilon_{i,t}
\]

where:

- \(F_t\) is the common inflation factor;
- \(\lambda_i\) is the loading of component \(i\);
- \(\varepsilon_{i,t}\) is idiosyncratic movement.

## 5.7 Interpretation

Underlying inflation is not a household cost-of-living measure. It is a persistence and breadth measure.

A high underlying rate suggests that inflation is becoming generalized rather than being driven by one or two categories.

## 5.8 Bias controls

- Do not switch methods based on which gives the preferred answer.
- Use the same hierarchy over time.
- Store the exact exclusion list or trim parameters.
- Do not mix official core CPI with a custom trimmed mean without labeling them separately.

---

# 6. Indicator 3 — Essential Cost Inflation

## 6.1 Question answered

How quickly are unavoidable or near-unavoidable household expenses increasing?

## 6.2 Concept

This indicator focuses on essential categories rather than the entire average consumer basket.

A default category set may include:

- basic food;
- rent or shelter;
- household energy;
- transportation required for work;
- essential healthcare;
- basic education;
- water;
- communications required for participation in modern life.

The category set must be documented and versioned.

## 6.3 Formula

\[
\pi^{essential}_t
=
\sum_{i \in E}
w^{essential}_i
\pi_{i,t}
\]

subject to:

\[
\sum_{i \in E}w^{essential}_i=1
\]

## 6.4 Weighting approaches

### Approach A — Official lower-income household weights

Preferred where available.

### Approach B — Expenditure survey weights

\[
w^{essential}_i
=
\frac{Expenditure_i}
{\sum_{j\in E}Expenditure_j}
\]

### Approach C — Standardized portfolio-project weights

Use only when local weights are unavailable. The fixed methodology must be disclosed and must not be presented as official.

## 6.5 Price-level version

For a fixed essential basket with quantities \(q_{i,0}\):

\[
ECI_t
=
\frac{
\sum_{i\in E}p_{i,t}q_{i,0}
}{
\sum_{i\in E}p_{i,0}q_{i,0}
}
\times100
\]

Then:

\[
\pi^{essential}_t
=
\left(
\frac{ECI_t}{ECI_{t-12}}-1
\right)\times100
\]

## 6.6 Interpretation

Essential Cost Inflation may exceed headline CPI when food, rent, energy, or transportation rise faster than discretionary goods.

It is especially relevant for lower-income households because essential expenses usually consume a larger share of income.

## 6.7 Limitations

- "Essential" is partly normative.
- Household needs differ by climate, region, age, and family structure.
- Publicly provided healthcare or education may reduce direct household costs.
- Subsidies may temporarily lower measured prices without lowering economic cost.

---

# 7. Indicator 4 — Fixed-Lifestyle Inflation

## 7.1 Question answered

How much more would it cost to preserve the same consumption pattern or lifestyle as in the reference period?

## 7.2 Purpose

This indicator prevents forced substitution from being interpreted as a cost improvement.

If a household previously purchased steak but later switches to a cheaper meal because steak became unaffordable, Fixed-Lifestyle Inflation continues to price the original steak basket.

## 7.3 Laspeyres-style formula

\[
FLI_t
=
\frac{
\sum_{i=1}^{n}p_{i,t}q_{i,0}
}{
\sum_{i=1}^{n}p_{i,0}q_{i,0}
}
\times100
\]

Inflation rate:

\[
\pi^{fixed}_t
=
\left(
\frac{FLI_t}{FLI_{t-12}}-1
\right)\times100
\]

## 7.4 Required inputs

- reference-period quantities;
- item-level prices;
- product matching rules;
- treatment of discontinued products;
- quality-adjustment policy.

## 7.5 Product replacement rule

When an item disappears, replacements must follow a documented hierarchy:

1. identical product;
2. same brand and size;
3. same specification and quality;
4. closest available equivalent;
5. category-level proxy.

Each replacement must receive a quality-confidence flag.

## 7.6 Shrinkflation adjustment

Use unit price:

\[
u_{i,t}
=
\frac{Price_{i,t}}{Quantity_{i,t}}
\]

Then compare equivalent units:

\[
\pi^{unit}_{i,t}
=
\left(
\frac{u_{i,t}}{u_{i,0}}-1
\right)\times100
\]

## 7.7 Quality adjustment

Two views are recommended:

- quality-adjusted official comparison;
- raw consumer-payment comparison.

Do not hide the difference.

## 7.8 Interpretation

Fixed-Lifestyle Inflation measures the cost of maintaining the same basket, not the minimum cost of maintaining the same utility.

It may overstate welfare loss when consumers willingly substitute toward better-value products. It may better reflect lived pressure when substitution is forced by declining affordability.

## 7.9 Status

This should be labeled as an experimental or project-defined indicator unless built directly from an official fixed-basket series.

---

# 8. Indicator 5 — Housing Inflation

## 8.1 Question answered

How much is the cost of obtaining and maintaining housing increasing?

## 8.2 Required subcomponents

Where data permits, calculate and display separately:

1. rent inflation;
2. owner-occupied housing acquisition inflation;
3. mortgage-payment inflation;
4. housing burden.

## 8.3 Rent inflation

\[
\pi^{rent}_t
=
\left(
\frac{RentIndex_t}{RentIndex_{t-12}}-1
\right)\times100
\]

## 8.4 House-price inflation

\[
\pi^{houseprice}_t
=
\left(
\frac{HPI_t}{HPI_{t-12}}-1
\right)\times100
\]

House prices are asset prices and must not be mislabeled as consumer inflation.

## 8.5 Mortgage-payment index

For a standard amortizing mortgage:

\[
PMT_t
=
L_t
\cdot
\frac{
r_t(1+r_t)^N
}{
(1+r_t)^N-1
}
\]

where:

- \(L_t\) is the representative loan amount;
- \(r_t\) is the periodic mortgage rate;
- \(N\) is the number of payment periods.

Mortgage-payment inflation:

\[
\pi^{mortgage}_t
=
\left(
\frac{PMT_t}{PMT_{t-12}}-1
\right)\times100
\]

## 8.6 Housing burden

\[
HousingBurden_t
=
\frac{
MonthlyHousingCost_t
}{
MonthlyDisposableIncome_t
}
\times100
\]

Housing cost may include:

- rent or mortgage payment;
- property tax;
- insurance;
- utilities;
- mandatory maintenance charges.

## 8.7 Optional housing pressure composite

A display score may be constructed:

\[
HPS_t
=
a\cdot z(\pi^{rent}_t)
+
b\cdot z(\pi^{mortgage}_t)
+
c\cdot z(HousingBurden_t)
\]

with:

\[
a+b+c=1
\]

This is a standardized pressure score, not an inflation rate.

## 8.8 Interpretation

Housing must remain multidimensional because renters, existing fixed-rate borrowers, new buyers, and outright homeowners experience different inflation.

---

# 9. Indicator 6 — Broad Money Expansion

## 9.1 Question answered

How quickly is liquid money and near-money expanding within the financial system?

## 9.2 Preferred source

Use the broadest consistently available official monetary aggregate, such as:

- M2;
- M3;
- broad money;
- money plus quasi-money.

Store the local definition.

## 9.3 Primary formula

\[
g^{money}_t
=
\left(
\frac{M_t}{M_{t-12}}-1
\right)\times100
\]

## 9.4 Per-capita money growth

\[
MPC_t
=
\frac{M_t}{Population_t}
\]

\[
g^{money,pc}_t
=
\left(
\frac{MPC_t}{MPC_{t-12}}-1
\right)\times100
\]

## 9.5 Broad money relative to real output

\[
MoneyOutputRatio_t
=
\frac{M_t}{RealGDP_t}
\]

Growth:

\[
g_t(M/RealGDP)
=
g_t(M)-g_t(RealGDP)
\]

approximately.

## 9.6 Interpretation

Broad Money Expansion is a monetary quantity indicator. It is not a consumer-price inflation rate.

It helps identify:

- monetary expansion;
- deposit creation;
- credit-driven liquidity growth;
- potential currency-dilution pressure;
- liquidity conditions that may affect goods, services, or asset prices.

## 9.7 Important limitation

An increase in broad money does not imply an equal increase in CPI because outcomes also depend on:

- real output;
- money demand;
- velocity;
- bank lending behavior;
- debt repayment;
- financial-market allocation;
- capital flows.

## 9.8 Terminology rule

Use "Broad Money Expansion" or "Monetary Expansion."

Do not label the value as "inflation" without a qualifier.

---

# 10. Indicator 7 — Excess Money Growth

## 10.1 Question answered

Is broad money expanding faster than real economic output?

## 10.2 Simple formula

\[
EMG_t
=
g_t(M)-g_t(Y)
\]

where:

- \(M\) is broad money;
- \(Y\) is real GDP or another real-output measure.

## 10.3 Quantity-equation context

Starting from:

\[
MV=PY
\]

Taking approximate growth rates:

\[
g(M)+g(V)
\approx
\pi+g(Y)
\]

Therefore:

\[
\pi
\approx
g(M)+g(V)-g(Y)
\]

A velocity-adjusted monetary pressure estimate is:

\[
MP_t
=
g_t(M)+g_t(V)-g_t(Y)
\]

## 10.4 Velocity definition

\[
V_t
=
\frac{NominalGDP_t}{M_t}
\]

Velocity growth:

\[
g_t(V)
=
\left(
\frac{V_t}{V_{t-k}}-1
\right)\times100
\]

## 10.5 Preferred outputs

Display:

- broad money growth;
- real GDP growth;
- simple excess money growth;
- velocity change;
- velocity-adjusted monetary pressure.

## 10.6 Interpretation

A positive Excess Money Growth value indicates that money is increasing faster than real output.

It is a pressure indicator, not a guaranteed CPI forecast.

## 10.7 Frequency rule

Do not combine monthly money growth with quarterly GDP growth without explicit alignment.

Options:

- convert all series to quarterly;
- use trailing-twelve-month growth;
- interpolate only with a visible estimate flag.

---

# 11. Indicator 8 — Producer and Import Inflation

## 11.1 Question answered

What upstream cost pressures may later affect consumer prices, company margins, or economic activity?

## 11.2 Core subcomponents

- producer prices;
- import prices;
- energy prices;
- commodity input prices;
- exchange-rate pass-through.

## 11.3 Producer-price inflation

\[
\pi^{ppi}_t
=
\left(
\frac{PPI_t}{PPI_{t-12}}-1
\right)\times100
\]

## 11.4 Import-price inflation

\[
\pi^{import}_t
=
\left(
\frac{IPI_t}{IPI_{t-12}}-1
\right)\times100
\]

## 11.5 Local-currency import-cost approximation

If foreign-currency price is \(P_t^{*}\) and the exchange rate is local currency per unit of foreign currency \(E_t\):

\[
P_t^{local}
=
P_t^{*}E_t
\]

Approximate growth:

\[
g(P^{local})
\approx
g(P^{*})+g(E)
\]

An exact discrete calculation is:

\[
1+g(P^{local})
=
(1+g(P^{*}))(1+g(E))
\]

## 11.6 Upstream pressure basket

\[
UPP_t
=
w_p\pi^{ppi}_t
+
w_i\pi^{import}_t
+
w_e\pi^{energy}_t
+
w_c\pi^{commodity}_t
\]

subject to:

\[
w_p+w_i+w_e+w_c=1
\]

## 11.7 Interpretation

Producer and Import Inflation is a leading or margin-pressure indicator.

A rise may be absorbed by:

- lower profit margins;
- productivity gains;
- subsidies;
- inventory changes;
- delayed price increases.

It should not be treated as future CPI with a one-to-one pass-through.

## 11.8 Country-specific context

For highly import-dependent economies, import prices and exchange rates may deserve greater weight.

For commodity exporters, domestic producer prices may rise while consumer prices remain moderated by subsidies or regulation.

---

# 12. Indicator 9 — Economy-Wide Inflation

## 12.1 Question answered

How much are prices changing across the country's total domestic production or domestic demand?

## 12.2 GDP deflator

\[
GDPDeflator_t
=
\frac{
NominalGDP_t
}{
RealGDP_t
}
\times100
\]

Inflation:

\[
\pi^{gdpdef}_t
=
\left(
\frac{GDPDeflator_t}{GDPDeflator_{t-4}}-1
\right)\times100
\]

for quarterly data.

## 12.3 Domestic demand deflator

Domestic demand:

\[
DD_t=C_t+I_t+G_t
\]

Deflator:

\[
DDDeflator_t
=
\frac{
NominalDD_t
}{
RealDD_t
}
\times100
\]

Inflation:

\[
\pi^{dd}_t
=
\left(
\frac{DDDeflator_t}{DDDeflator_{t-4}}-1
\right)\times100
\]

## 12.4 Interpretation

GDP deflator covers domestically produced final goods and services. It differs from CPI because:

- it includes investment and government output;
- it includes exports;
- it excludes imports directly;
- its weights change with the composition of production.

Domestic demand deflator may better reflect prices paid within the economy because it includes imports and excludes exports.

## 12.5 Preferred display

If both are available, show both.

Do not average them automatically because they answer different questions.

---

# 13. Indicator 10 — Purchasing-Power Squeeze

## 13.1 Question answered

Are wages or household incomes keeping up with the prices people actually face?

## 13.2 Real wage growth using headline CPI

Exact form:

\[
g^{realwage}_t
=
\left[
\frac{
1+g^{nominalwage}_t
}{
1+\pi^{headline}_t
}
-1
\right]\times100
\]

Approximation:

\[
g^{realwage}_t
\approx
g^{nominalwage}_t-\pi^{headline}_t
\]

## 13.3 Essential-cost-adjusted wage growth

\[
g^{realwage,essential}_t
=
\left[
\frac{
1+g^{nominalwage}_t
}{
1+\pi^{essential}_t
}
-1
\right]\times100
\]

## 13.4 Disposable-income version

\[
g^{realincome}_t
=
\left[
\frac{
1+g^{disposableincome}_t
}{
1+\pi_t
}
-1
\right]\times100
\]

## 13.5 Purchasing-power squeeze

Define squeeze as the negative of real growth when inflation exceeds income growth:

\[
PPS_t
=
\pi_t-g^{nominalincome}_t
\]

A positive value means prices are rising faster than nominal income.

## 13.6 Dual reporting requirement

Display at least:

- wage growth minus headline CPI;
- wage growth minus Essential Cost Inflation.

Optional:

- median wage;
- mean wage;
- disposable income;
- lower-income household income.

## 13.7 Interpretation

This indicator focuses on welfare and affordability rather than prices alone.

An economy can have moderate CPI while households experience a squeeze if:

- wages lag;
- taxes rise;
- essential costs rise faster than headline CPI;
- housing costs increase sharply;
- income gains are concentrated among high earners.

---

# 14. Cross-Indicator Reading Framework

The ten indicators should be interpreted together.

## Scenario A — CPI high, money growth low

Possible causes:

- energy shock;
- import-price shock;
- supply disruption;
- currency depreciation;
- tax increase.

## Scenario B — money growth high, CPI low

Possible causes:

- falling velocity;
- liquidity trapped in financial assets;
- weak demand;
- debt repayment;
- rising money demand;
- delayed pass-through.

## Scenario C — CPI moderate, essential inflation high

Likely household affordability pressure, especially for lower-income groups.

## Scenario D — CPI moderate, housing inflation high

Potential intergenerational or renter-versus-owner divergence.

## Scenario E — wages rise slower than essential inflation

Living standards may be falling even when official real wages appear stable under headline CPI.

---

# 15. Optional Dashboard Grouping

The ten indicators may be grouped into four non-exclusive dimensions.

## 15.1 Cost of Living

- Headline Consumer Inflation
- Essential Cost Inflation
- Fixed-Lifestyle Inflation
- Housing Inflation

## 15.2 Persistence

- Underlying Inflation

## 15.3 Monetary and Upstream Pressure

- Broad Money Expansion
- Excess Money Growth
- Producer and Import Inflation

## 15.4 Economy and Welfare

- Economy-Wide Inflation
- Purchasing-Power Squeeze

Do not call a dimension score an inflation rate unless it is mathematically an index-rate calculation.

---

# 16. Optional Composite Score

A composite score is allowed only as a presentation aid.

It must not be labeled "True Inflation."

## 16.1 Standardization

For indicator \(x_i\):

\[
z_i
=
\frac{
x_i-\mu_i
}{
\sigma_i
}
\]

where \(\mu_i\) and \(\sigma_i\) are defined using a documented historical window.

## 16.2 Composite

\[
Score_t
=
\sum_{i=1}^{n}w_i z_{i,t}
\]

subject to:

\[
\sum_iw_i=1
\]

## 16.3 Required disclosures

- selected indicators;
- weights;
- standardization window;
- missing-data treatment;
- whether weights are fixed or user-adjustable;
- methodology version.

A composite score must remain separate from official inflation rates.

---

# 17. Data Quality and Confidence

## 17.1 Suggested confidence levels

### High

- official national source;
- current release;
- clear methodology;
- no estimation;
- correct frequency alignment.

### Medium

- reputable international source;
- delayed release;
- minor mapping assumptions;
- partial category coverage.

### Low

- estimated;
- unofficial;
- stale;
- incomplete;
- methodology mismatch;
- AI-assisted discovery not manually verified.

## 17.2 Suggested machine-readable fields

```json
{
  "country": "THA",
  "indicator_id": "broad_money_expansion",
  "value": 4.8,
  "unit": "percent_yoy",
  "period": "2026-06",
  "source_name": "Official Central Bank",
  "source_series_id": "SERIES_CODE",
  "publication_date": "2026-07-31",
  "seasonally_adjusted": false,
  "methodology_version": "1.0.0",
  "confidence": "high",
  "coverage": "full",
  "is_estimated": false
}
```

---

# 18. Country Search and AI Mapping Guidelines

AI may help resolve country-specific terminology, but the result must be validated against a source registry.

## 18.1 Country resolution

Map user text to:

- ISO 3166-1 alpha-2;
- ISO 3166-1 alpha-3;
- canonical country name;
- local-language country name.

## 18.2 Indicator keyword expansion

Examples:

- CPI;
- consumer price index;
- cost-of-living index;
- headline inflation;
- broad money;
- M2;
- M3;
- money and quasi-money;
- producer price index;
- import price index;
- GDP deflator;
- wage index;
- house price index.

## 18.3 Source hierarchy

1. national statistics office;
2. central bank;
3. finance or economy ministry;
4. supranational statistical authority;
5. IMF, World Bank, OECD, BIS, or equivalent;
6. secondary provider with explicit provenance.

## 18.4 AI safety rule

AI output must generate a candidate mapping, not a final numeric observation.

A numeric value enters the system only after deterministic parsing and validation.

---

# 19. Versioning Rules

Any change to the following requires a methodology version update:

- formula;
- weighting scheme;
- category definition;
- source hierarchy;
- missing-data treatment;
- seasonal-adjustment policy;
- product-replacement rule;
- quality-adjustment policy;
- composite-score design.

Use semantic versioning:

- major: incompatible methodology change;
- minor: new optional feature or indicator refinement;
- patch: correction that does not change intended meaning.

---

# 20. Final Implementation Rule

The website should present inflation as a set of measurable pressures, not as one unquestionable number.

Every displayed result must answer four questions:

1. What is being measured?
2. How is it calculated?
3. What does it capture?
4. What does it miss?
