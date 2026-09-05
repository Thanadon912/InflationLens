/* Stress: find the breaking point, on purpose.
 *
 * Steps the load past what the API is expected to handle until something
 * gives -- latency knees, errors appear, or throughput stops rising while
 * VUs keep climbing. Every one of those is visible in the dashboard's
 * "Virtual users & throughput" panel, which is the point of the run.
 *
 * A FAIL here is the expected outcome, not a regression: the run answers
 * "where does it break", and the answer is only useful if it actually
 * breaks. Read the p95 curve and the per-endpoint table, not the verdict
 * tile.
 */

import { sleep } from 'k6';

import { thresholds } from './lib/slo.js';
import { loadContracts, pageLoad, cachedIndicator, calculateCountry } from './lib/journey.js';

export const options = {
  scenarios: {
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 20 },
        { duration: '2m', target: 50 },
        { duration: '2m', target: 100 },
        { duration: '2m', target: 150 },
        { duration: '2m', target: 200 },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '15s',
    },
  },
  // Recorded, never aborted on: stopping at the first breach would cut
  // the run off exactly where its findings begin.
  thresholds: thresholds(),
};

export function setup() {
  return { contracts: loadContracts() };
}

export default function (data) {
  pageLoad('USA');
  if (Math.random() < 0.3) cachedIndicator('USA');
  if (Math.random() < 0.1) calculateCountry(data.contracts);
  sleep(0.5);
}
