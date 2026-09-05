/* Smoke: one virtual user, every endpoint, once per iteration.
 *
 * Not a load test. This proves the harness itself is sound -- the server
 * is up, the cache is seeded, and every POST body still satisfies the
 * calculation contract -- before a long run spends ten minutes producing
 * numbers that only measure a misconfiguration. Run it first, always.
 */

import { sleep } from 'k6';

import { thresholds } from './lib/slo.js';
import {
  loadContracts, pageLoad, search, cachedIndicator,
  calculateCountry, calculateCountryDashboard, calculateGlobalDashboard, health,
} from './lib/journey.js';

export const options = {
  scenarios: {
    smoke: { executor: 'constant-vus', vus: 1, duration: '30s' },
  },
  thresholds: thresholds(),
};

export function setup() {
  return { contracts: loadContracts() };
}

export default function (data) {
  const { contracts } = data;

  health();
  pageLoad('USA');
  pageLoad('EA');
  search();
  cachedIndicator('USA');
  calculateCountry(contracts);
  calculateCountryDashboard(contracts);
  calculateGlobalDashboard(contracts);

  sleep(1);
}
