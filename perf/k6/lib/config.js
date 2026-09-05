/* Shared configuration for every scenario.
 *
 * Nothing here is scenario-specific: base URL, the tags that identify a
 * run in Prometheus, and the request helpers that make the per-endpoint
 * table in Grafana readable.
 */

import http from 'k6/http';
import { check } from 'k6';

// 5055, not 5000: the Playwright E2E suite owns 5000 and adopts whatever
// is already listening there. perf/scripts/run.sh passes this explicitly;
// the default only matters when running k6 by hand.
export const BASE_URL = `${__ENV.BASE_URL || 'http://127.0.0.1:5055'}/api/v1`;

/* Every request carries a `name` tag. Without it k6 tags the time series
 * with the full URL, so `/measures/USA?window=12m` and
 * `?window=6m` become separate rows -- the per-endpoint table would grow
 * a row per query-string combination and stop being scannable. `kind`
 * splits read (cache lookup) from calc (engine work), which the SLO
 * thresholds select on. */
export function get(path, name, extraTags = {}) {
  return http.get(`${BASE_URL}${path}`, {
    tags: { name, kind: 'read', ...extraTags },
  });
}

export function post(path, body, name, extraTags = {}) {
  return http.post(`${BASE_URL}${path}`, JSON.stringify(body), {
    headers: { 'Content-Type': 'application/json' },
    tags: { name, kind: 'calc', ...extraTags },
  });
}

/* Assert on the response body, not just the status code.
 *
 * A misconfigured or unseeded cache still answers 200 -- with an empty
 * payload, and faster than a real one. Checking only `status === 200`
 * would report that as an excellent result. `body` receives the parsed
 * JSON, or null when the response was not parseable JSON.
 */
export function verify(res, name, assertions) {
  let body = null;
  try {
    body = res.json();
  } catch (_) {
    body = null;
  }
  const checks = { [`${name}: status 200`]: (r) => r.status === 200 };
  for (const [label, predicate] of Object.entries(assertions)) {
    checks[`${name}: ${label}`] = () => body !== null && predicate(body);
  }
  check(res, checks, { name });
  return body;
}
