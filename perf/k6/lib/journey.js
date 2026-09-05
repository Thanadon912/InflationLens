/* The load the front end actually generates.
 *
 * Front-end/data.js fires five GETs in parallel on every page load and
 * every geography/window/adjustment change, so that batch -- not a
 * round-robin over one endpoint at a time -- is the unit of load worth
 * measuring. Hitting endpoints one by one would understate the concurrent
 * pressure on the SQLite cache, which is the whole thing under test.
 */

import http from 'k6/http';
import { check } from 'k6';

import { BASE_URL, get, post, reject, verify } from './config.js';
import { body, countryDashboardBody, globalDashboardBody } from './payloads.js';

const WINDOWS = ['12m', '1m', '6m'];
const ADJUSTMENTS = ['as_published', 'sa', 'nsa'];
const SEARCHES = ['usa', 'united', 'euro', 'eurozone', 'america'];

function pick(list) {
  return list[Math.floor(Math.random() * list.length)];
}

/* Fetch the published contract once, in setup(), and hand it to every VU.
 * Building POST bodies from what the API says it accepts today means a
 * contract change surfaces as a failed check rather than as a payload that
 * quietly drifted out of date. */
export function loadContracts() {
  const res = http.get(`${BASE_URL}/meta/indicators`, { tags: { name: 'GET /meta/indicators', kind: 'read' } });
  if (res.status !== 200) {
    throw new Error(`cannot read the indicator contract at ${BASE_URL}/meta/indicators: HTTP ${res.status}`);
  }
  return res.json();
}

/* One page load: the five-request batch data.js issues, verified on
 * content rather than status alone. */
export function pageLoad(geo = 'USA') {
  const win = pick(WINDOWS);
  const adjustment = pick(ADJUSTMENTS);

  // data.js requests categories and regions only for USA -- the category
  // ladder and the state choropleth are US-only views. Issuing them for EA
  // too would inflate the request count with traffic the product never
  // generates, so the batch is built the same way data.js builds it.
  const requests = [
    ['GET', `${BASE_URL}/measures/${geo}?window=${win}&adjustment=${adjustment}`, null, { tags: { name: 'GET /measures/{geo}', kind: 'read' } }],
    ['GET', `${BASE_URL}/world/cross-section`, null, { tags: { name: 'GET /world/cross-section', kind: 'read' } }],
    ['GET', `${BASE_URL}/meta/data-sources`, null, { tags: { name: 'GET /meta/data-sources', kind: 'read' } }],
  ];
  if (geo === 'USA') {
    requests.push(
      ['GET', `${BASE_URL}/categories/USA`, null, { tags: { name: 'GET /categories/{geo}', kind: 'read' } }],
      ['GET', `${BASE_URL}/regions/us`, null, { tags: { name: 'GET /regions/us', kind: 'read' } }],
    );
  }

  const responses = http.batch(requests);
  const [measures, world, sources, categories, regions] = responses;

  // The sa/nsa rails filter the ledger, and filtering can legitimately
  // empty it: EA publishes only the NSA HICP, so `?adjustment=sa` on EA
  // correctly returns zero measures. Assert the shape unconditionally,
  // the seven-measure US ledger where it is guaranteed, and values only
  // where a row came back at all.
  verify(measures, 'GET /measures/{geo}', {
    'ledger is an array': (b) => Array.isArray(b.measures) && b.geography === geo,
    'us ledger complete': (b) => geo !== 'USA' || adjustment !== 'as_published' || b.measures.length === 7,
    'rows carry values': (b) => b.measures.length === 0 || b.measures.some((m) => m.yoy !== null),
  });
  // Only present on the USA batch, per the conditional above.
  if (categories) {
    verify(categories, 'GET /categories/{geo}', {
      'categories present': (b) => Array.isArray(b.categories) && b.categories.length > 0,
    });
  }
  if (regions) {
    verify(regions, 'GET /regions/us', {
      'four census regions': (b) => Object.keys(b.regions || {}).length === 4,
      'states inherited': (b) => Object.keys(b.stateValues || {}).length > 40,
    });
  }
  verify(world, 'GET /world/cross-section', {
    'cross-section populated': (b) => b.economies > 100,
    'median computed': (b) => typeof b.median === 'number',
  });
  verify(sources, 'GET /meta/data-sources', {
    'publishers listed': (b) => Array.isArray(b.publishers) && b.publishers.length > 0,
  });
}

/* The search rail. Cheap, and the only endpoint that takes free text. */
export function search() {
  const q = pick(SEARCHES);
  const res = get(`/resolve?q=${q}`, 'GET /resolve');
  verify(res, 'GET /resolve', { 'match found': (b) => Array.isArray(b.matches) && b.matches.length > 0 });
}

/* Cached single-indicator read -- the endpoint an API consumer polls,
 * as opposed to the batch the browser issues. */
export function cachedIndicator(geo = 'USA') {
  const res = get(`/country/${geo}/headline_consumer_inflation`, 'GET /country/{geo}/{indicator}');
  verify(res, 'GET /country/{geo}/{indicator}', {
    'value present': (b) => b.value !== null && b.value !== undefined,
  });
}

/* A single country calculation: one engine, one request. */
export function calculateCountry(contracts, indicatorId = 'fixed_lifestyle_inflation') {
  const res = post(
    `/country/USA/${indicatorId}`,
    body(indicatorId, contracts.country[indicatorId].api_contract),
    'POST /country/{geo}/{indicator}',
  );
  verify(res, 'POST /country/{geo}/{indicator}', {
    'full coverage': (b) => b.coverage === 'full',
  });
}

/* The heaviest paths in the API: every engine in one request. Each
 * indicator that fails comes back `unavailable` rather than failing the
 * request, so checking the *count* of available results is what actually
 * proves the engines ran. */
export function calculateCountryDashboard(contracts, opts) {
  const expected = Object.keys(contracts.country).length;
  const res = post('/country/USA/dashboard', countryDashboardBody(contracts, opts), 'POST /country/{geo}/dashboard');
  verify(res, 'POST /country/{geo}/dashboard', {
    'all indicators computed': (b) =>
      Array.isArray(b.indicators) &&
      b.indicators.length === expected &&
      b.indicators.every((i) => i.coverage !== 'unavailable'),
  });
}

export function calculateGlobalDashboard(contracts, opts) {
  const expected = Object.keys(contracts.global).length;
  const res = post('/global/dashboard', globalDashboardBody(contracts, opts), 'POST /global/dashboard');
  verify(res, 'POST /global/dashboard', {
    'all indicators computed': (b) =>
      Array.isArray(b.indicators) &&
      b.indicators.length === expected &&
      b.indicators.every((i) => i.coverage !== 'unavailable'),
  });
}

/* Requests the API is supposed to refuse.
 *
 * Every other helper in this file sends a well-formed request, which
 * leaves the whole refusal path unmeasured -- and the refusal path is the
 * one an attacker drives. What matters is not that these return an error
 * but *what they cost*: if rejecting a request is more expensive than
 * serving a real one, then bad traffic is an amplifier, and an API with
 * no rate limiting (README.md: open by design) has no second line of
 * defence behind that.
 *
 * Each case is asserted on the structured error envelope
 * (app/api/errors.py), not merely on the status code. A stack trace, an
 * empty body, or a generic proxy error page would all arrive with the
 * right status and the wrong contents.
 *
 * Statuses and codes here were read off the running API, not assumed.
 */
const REJECTIONS = [
  { method: 'GET', path: '/measures/ZZZ', status: 404, code: 'DATA_SNAPSHOT_NOT_FOUND',
    name: 'GET /measures/{geo} [unknown geo]' },
  { method: 'GET', path: '/measures/USA?window=banana', status: 400, code: 'SCHEMA_ERROR',
    name: 'GET /measures/{geo} [bad window]' },
  { method: 'GET', path: '/country/USA/not_a_real_indicator', status: 404, code: 'DATA_SNAPSHOT_NOT_FOUND',
    name: 'GET /country/{geo}/{indicator} [unknown indicator]' },
  { method: 'POST', path: '/country/USA/fixed_lifestyle_inflation', status: 400, code: 'SCHEMA_ERROR',
    body: '{"period": ', name: 'POST /country/{geo}/{indicator} [malformed JSON]' },
  { method: 'POST', path: '/country/USA/no_such_indicator', status: 404, code: 'INDICATOR_NOT_FOUND',
    body: '{"period":"2026-07","inputs":{}}', name: 'POST /country/{geo}/{indicator} [unknown indicator]' },
];

/* One oversized body, built once per VU rather than per iteration.
 *
 * app/factory.py caps request bodies at 2 MiB specifically to stop
 * oversized payloads reaching the JSON parser, but nothing until now
 * checked that the cap is actually cheaper than accepting the body would
 * be. Just over the limit is the interesting size: comfortably rejected,
 * while still making the client push the whole thing. */
const OVERSIZED_BODY = `{"period":"2026-07","pad":"${'x'.repeat(2 * 1024 * 1024 + 1024)}"}`;

export function malformedRequest() {
  const c = REJECTIONS[Math.floor(Math.random() * REJECTIONS.length)];
  const res = reject(c.method, c.path, c.status, c.name, c.body || null,
    c.body ? { 'Content-Type': 'application/json' } : {});
  verify(res, c.name, { 'structured error envelope': (b) => b.error && b.error.code === c.code }, c.status);
}

export function oversizedBody() {
  const name = 'POST /country/{geo}/{indicator} [body over 2 MiB]';
  const res = reject('POST', '/country/USA/fixed_lifestyle_inflation', 413, name,
    OVERSIZED_BODY, { 'Content-Type': 'application/json' });
  verify(res, name, { 'structured error envelope': (b) => b.error && b.error.code === 'HTTP_413' }, 413);
}

/* Cheap liveness probe, used by the spike scenario to tell "the server is
 * slow" apart from "the server is gone". */
export function health() {
  const res = get('/health', 'GET /health');
  check(res, { 'GET /health: status 200': (r) => r.status === 200 });
}
