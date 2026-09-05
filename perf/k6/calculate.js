/* Calculate: the CPU-bound POST path, driven at a fixed arrival rate.
 *
 * Every other scenario uses VUs, where each VU waits for its response
 * before sending the next request. That is right for a browser, and wrong
 * here: as the engines slow down, VU-driven load throttles itself, and
 * the test quietly stops pushing exactly when the server starts
 * struggling. A constant arrival rate keeps sending regardless, so
 * saturation shows up as a growing queue rather than as a flat line.
 *
 * The dashboard tell is `k6_vus` climbing toward maxVUs while throughput
 * stays flat: k6 is allocating more and more VUs to sustain the rate,
 * which means the API is no longer keeping up.
 */

import { thresholds } from './lib/slo.js';
import { ISO3 } from './lib/payloads.js';
import { loadContracts, calculateCountry, calculateCountryDashboard, calculateGlobalDashboard } from './lib/journey.js';

/* How many economies the global payloads carry. Ten keeps the global
 * dashboard body around 225 KB, which is engine-bound. Raising it makes the
 * request bigger faster than it makes the aggregation harder, so past ~40
 * the run measures JSON parsing rather than the engines -- and the API
 * rejects anything over 2 MiB outright (app/factory.py). */
const COUNTRIES = ISO3.slice(0, Number(__ENV.COUNTRIES || 10));

export const options = {
  scenarios: {
    calculate: {
      executor: 'constant-arrival-rate',
      // 30/s was the first figure tried and it sustained on a single VU --
      // a rate the API absorbs without effort measures nothing. 200/s puts
      // the engines under real pressure. Raise it (`RATE=400
      // ./perf/scripts/run.sh calculate`) to walk toward the actual ceiling.
      rate: Number(__ENV.RATE || 200),
      timeUnit: '1s',
      duration: '3m',
      preAllocatedVUs: 50,
      // Headroom for k6 to reveal saturation. If the run ends with
      // `dropped_iterations` above zero, even this was not enough and the
      // API is well past its limit.
      maxVUs: 200,
    },
  },
  thresholds: thresholds(),
};

export function setup() {
  return { contracts: loadContracts() };
}

export default function (data) {
  const { contracts } = data;
  const opts = { countries: COUNTRIES };
  const roll = Math.random();

  // Weighted toward the single-indicator call, which is what an API
  // consumer actually polls; the two dashboards are the heavy tail.
  if (roll < 0.6) {
    calculateCountry(contracts);
  } else if (roll < 0.85) {
    calculateCountryDashboard(contracts, opts);
  } else {
    calculateGlobalDashboard(contracts, opts);
  }
}
