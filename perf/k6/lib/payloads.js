/* Valid POST bodies for every calculation endpoint.
 *
 * The API refuses anonymous numbers: each input role must carry an array
 * of fully provenanced, normalized observations (Back-end/app/api/
 * contracts.py), and the observation shape here mirrors the one the
 * backend's own contract tests use (Back-end/tests/integration/
 * test_strict_contract.py).
 *
 * Built in code rather than checked in as static JSON so the global
 * payloads can be scaled -- `globalBody(id, 40)` produces a
 * forty-economy request, which is what makes the global engines do real
 * aggregation work instead of averaging ten numbers.
 *
 * Every body here has been verified to return HTTP 200 with
 * `coverage: "full"`; the smoke scenario re-asserts that on each run, so
 * a contract change surfaces as a failed check rather than as a
 * mysteriously fast test.
 */

// Roles whose observations are a keyed mapping (one observation per
// component or country) rather than a single scalar.
const MAPPING_ROLES = new Set([
  'component_rates', 'component_weights', 'category_rates', 'prices_current',
  'prices_prior_year', 'prices_base', 'quantities_base', 'package_sizes_current',
  'package_sizes_base', 'country_headline_rates', 'quality_adjusted_prices_current',
  'country_weights', 'country_price_relatives', 'country_rates', 'population_by_geo',
  'gdp_ppp_by_geo', 'consumption_ppp_by_geo', 'country_essential_rates',
  'consumption_ppp_weights', 'population_weights', 'country_money_growth_rates',
  'gdp_ppp_weights', 'country_money_growth', 'country_real_gdp_growth',
  'country_velocity_adjusted_mp', 'country_ppi_rates', 'country_import_rates',
  'import_share_weights', 'commodity_rates', 'commodity_weights',
  'country_house_price_current', 'country_house_price_prior', 'housing_weights',
  'country_rent_rates', 'country_rates_current', 'country_rates_prior',
]);

// Global requests must additionally declare these three coverage measures,
// which the coverage-threshold gate in the API checks before accepting a
// global result.
const COVERAGE_ROLES = ['population_by_geo', 'gdp_ppp_by_geo', 'consumption_ppp_by_geo'];

// A handful of roles must be tagged with the normalized indicator they
// were derived from, not the indicator being calculated.
const SOURCE_INDICATOR = {
  country_headline_rates: 'headline_consumer_inflation',
  country_rates: 'headline_consumer_inflation',
  country_rates_current: 'headline_consumer_inflation',
  country_rates_prior: 'headline_consumer_inflation',
  country_essential_rates: 'essential_cost_inflation',
  country_money_growth_rates: 'broad_money_expansion',
  country_money_growth: 'broad_money_expansion',
};

const COMPONENTS = ['food', 'housing', 'energy', 'transport', 'healthcare', 'communications'];
const COMPONENT_INDICATORS = new Set([
  'underlying_inflation', 'essential_cost_inflation', 'fixed_lifestyle_inflation',
]);

const ISO3 = [
  'USA', 'CHN', 'JPN', 'DEU', 'IND', 'GBR', 'FRA', 'BRA', 'ITA', 'CAN',
  'KOR', 'RUS', 'AUS', 'ESP', 'MEX', 'IDN', 'NLD', 'SAU', 'TUR', 'CHE',
  'POL', 'ARG', 'SWE', 'BEL', 'THA', 'IRL', 'AUT', 'NGA', 'ISR', 'NOR',
  'ZAF', 'EGY', 'DNK', 'SGP', 'MYS', 'PHL', 'VNM', 'CHL', 'FIN', 'PRT',
];

// Fixed periods. The contract enforces exact period alignment per role,
// and pinning them keeps every run's request bytes identical so two runs
// stay comparable.
const TARGET = { monthly: '2026-07', quarterly: '2026-Q2', annual: '2026' };
const PRIOR = { monthly: '2025-07', quarterly: '2025-Q2', annual: '2025' };
const PREVIOUS = { monthly: '2026-06', quarterly: '2026-Q1', annual: '2025' };

// Roles that legitimately carry their own lag rather than the requested
// period, and how far back the contract expects each to sit.
function periodFor(role, frequency, target) {
  if (role.endsWith('_prior') || role.endsWith('_prior_year') || role.endsWith('_base')) {
    return PRIOR[frequency];
  }
  if (role.endsWith('_previous_period')) return PREVIOUS[frequency];
  return target;
}

function isWeightOrCoverage(role) {
  return role.includes('weight') || COVERAGE_ROLES.indexOf(role) !== -1;
}

/* The contract accepts several units per role and reports them
 * alphabetically. Alphabetical order is not meaningful -- `currency`
 * sorts before `index` for a CPI series -- so pick by intent. */
function pickUnit(units) {
  for (const preferred of ['index', 'percent_yoy', 'ratio', 'persons', 'local_currency']) {
    if (units.indexOf(preferred) !== -1) return preferred;
  }
  return units[0];
}

function valueFor(unit, i) {
  switch (unit) {
    case 'percent_yoy': return round(2.0 + i * 0.3);
    case 'index': return round(100.0 + i * 3);
    case 'ratio': return 1.0;
    case 'share_percent': return 100.0;
    case 'persons': return 1000000.0 * (i + 1);
    case 'currency_per_unit': return round(10.0 + i);
    default: return round(1000.0 + i * 50); // currency / local_currency
  }
}

function round(n, places = 4) {
  const f = Math.pow(10, places);
  return Math.round(n * f) / f;
}

function observation(role, indicatorId, value, period, frequency, unit, componentId) {
  const o = {
    provider: 'official-test',
    source_series_id: `SERIES:${role}:${componentId || 'USA'}`,
    indicator_id: SOURCE_INDICATOR[role] || indicatorId,
    geography: 'USA',
    frequency,
    unit,
    observation_period: period,
    value,
    retrieved_at: '2026-08-01T00:00:00Z',
    validation_status: 'validated',
    source_url: 'https://example.test/official',
    data_vintage: '2026-08-01',
  };
  if (componentId) o.component_id = componentId;
  return o;
}

function buildRole(indicatorId, role, units, frequency, target, countries) {
  let unit = pickUnit(units);
  let period = periodFor(role, frequency, target);
  let freq = frequency;

  // Weights and coverage measures are always annual and always dated to
  // the year before the requested period.
  if (isWeightOrCoverage(role)) {
    unit = units.indexOf('ratio') !== -1 ? 'ratio' : units[0];
    period = String(Number(target.slice(0, 4)) - 1);
    freq = 'annual';
  }

  if (!MAPPING_ROLES.has(role)) {
    const scale = period === target ? 1.0 : 0.97;
    return [observation(role, indicatorId, round(valueFor(unit, 1) * scale), period, freq, unit)];
  }

  const commodity = role === 'commodity_rates' || role === 'commodity_weights';
  const keys = COMPONENT_INDICATORS.has(indicatorId) || commodity ? COMPONENTS : countries;

  if (role.includes('weight')) {
    // Weights must sum to exactly 1 within 1e-6, so the last key absorbs
    // the rounding remainder rather than every key carrying 1/n.
    const share = round(1.0 / keys.length, 6);
    return keys.map((key, i) => observation(
      role, indicatorId,
      i === keys.length - 1 ? round(1.0 - share * (keys.length - 1), 6) : share,
      period, freq, unit, key,
    ));
  }

  const scale = period === target ? 1.0 : 0.97;
  return keys.map((key, i) => observation(
    role, indicatorId, round(valueFor(unit, i) * scale), period, freq, unit, key,
  ));
}

/* Gold and bitcoin prices in two currencies. This one indicator takes its
 * asset prices through `options` as a nested {asset: {currency: price}}
 * map rather than as observations, and without it the engine reports
 * partial coverage and skips its asset components entirely. */
const ASSET_PRICE_OPTIONS = {
  asset_prices_current: {
    gold: { USD: 2400.0, EUR: 2210.0 },
    bitcoin: { USD: 95000.0, EUR: 87400.0 },
  },
  asset_prices_prior_year: {
    gold: { USD: 2150.0, EUR: 2010.0 },
    bitcoin: { USD: 71000.0, EUR: 66200.0 },
  },
};

/* Build one indicator's request body from the contract the API itself
 * publishes at GET /meta/indicators, so a contract change shows up as a
 * failed check here instead of silently drifting out of date.
 *
 * `contract` is that endpoint's `api_contract` block; `countries` sets how
 * wide the per-country mappings are. */
export function body(indicatorId, contract, { global = false, countries = ISO3.slice(0, 10) } = {}) {
  const frequency = contract.accepted_frequencies[0];
  const target = TARGET[frequency];

  const roles = contract.required_roles.concat(contract.optional_roles);
  if (global) roles.push(...COVERAGE_ROLES);

  const inputs = {};
  for (const role of roles) {
    if (inputs[role]) continue;
    inputs[role] = buildRole(indicatorId, role, contract.role_units[role], frequency, target, countries);
  }

  // Headline CPI is the one role that carries two periods in one array:
  // the engine derives its own year-over-year from the index series.
  if (indicatorId === 'headline_consumer_inflation') {
    const unit = pickUnit(contract.role_units.all_items_cpi_index);
    inputs.all_items_cpi_index = [
      observation('all_items_cpi_index', indicatorId, 330.0, target, frequency, unit),
      observation('all_items_cpi_index', indicatorId, 320.0, PRIOR[frequency], frequency, unit),
    ];
  }

  const out = { period: target, inputs };
  if (indicatorId === 'global_housing_asset_inflation') out.options = ASSET_PRICE_OPTIONS;
  if (global) out.universe = countries;
  return out;
}

/* Every country indicator keyed by id -- the shape POST
 * /country/{geo}/dashboard expects. */
export function countryDashboardBody(contracts, opts) {
  const out = {};
  for (const [id, definition] of Object.entries(contracts.country)) {
    out[id] = body(id, definition.api_contract, { ...opts, global: false });
  }
  return out;
}

export function globalDashboardBody(contracts, opts) {
  const out = {};
  for (const [id, definition] of Object.entries(contracts.global)) {
    out[id] = body(id, definition.api_contract, { ...opts, global: true });
  }
  return out;
}

export { ISO3 };
