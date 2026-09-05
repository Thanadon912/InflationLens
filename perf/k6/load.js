/* Load: the traffic shape this API is expected to survive.
 *
 * Twenty concurrent browsers on the workbench, held long enough that the
 * numbers are a steady state rather than a warm-up artifact. This is the
 * run whose PASS/FAIL means "the API is healthy"; the other scenarios
 * exist to find its edges, not to gate a release.
 *
 * The mix is weighted the way real use is: most traffic is the front
 * end's read batch, a minority is API consumers posting calculations.
 */

import { sleep } from 'k6';

import { thresholds } from './lib/slo.js';
import {
  loadContracts, pageLoad, search, cachedIndicator,
  calculateCountry, calculateCountryDashboard,
} from './lib/journey.js';

export const options = {
  scenarios: {
    load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 20 },  // ramp in
        { duration: '3m', target: 20 },  // steady state -- the numbers that matter
        { duration: '30s', target: 0 },  // ramp out
      ],
      gracefulRampDown: '15s',
    },
  },
  thresholds: thresholds(),
};

export function setup() {
  return { contracts: loadContracts() };
}

export default function (data) {
  const { contracts } = data;

  // ~70% of iterations are a plain page load, matching a workbench user
  // clicking between geographies far more often than anyone POSTs.
  pageLoad(Math.random() < 0.8 ? 'USA' : 'EA');

  const roll = Math.random();
  if (roll < 0.4) {
    search();
  } else if (roll < 0.7) {
    cachedIndicator('USA');
  } else if (roll < 0.9) {
    calculateCountry(contracts);
  } else {
    calculateCountryDashboard(contracts);
  }

  sleep(Math.random() * 2 + 0.5); // 0.5-2.5s think time
}
