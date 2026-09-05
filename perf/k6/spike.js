/* Spike: a sudden surge, and whether the API comes back from it.
 *
 * Stress asks how much load breaks the API. Spike asks a different
 * question: after the surge passes, does latency return to baseline, or
 * does the API stay degraded? A queue that never drains, a connection
 * pool that never recovers, and a SQLite writer stuck behind a lock all
 * look identical during the spike and quite different after it.
 *
 * So the tail matters more than the peak here: read the last two minutes
 * of the "Response time over time" panel and compare them to the first.
 */

import { sleep } from 'k6';

import { thresholds } from './lib/slo.js';
import { loadContracts, pageLoad, health } from './lib/journey.js';

export const options = {
  scenarios: {
    spike: {
      executor: 'ramping-vus',
      startVUs: 5,
      stages: [
        { duration: '1m', target: 5 },    // baseline to compare the recovery against
        { duration: '10s', target: 200 }, // surge
        { duration: '30s', target: 200 },
        { duration: '10s', target: 5 },   // drop
        { duration: '2m', target: 5 },    // recovery window -- the part worth reading
      ],
      gracefulRampDown: '15s',
    },
  },
  thresholds: thresholds(),
};

export function setup() {
  return { contracts: loadContracts() };
}

export default function () {
  // Health is checked every iteration so the dashboard can distinguish
  // "slow" from "gone": if /health keeps answering while the read batch
  // times out, the process is alive and the bottleneck is downstream.
  health();
  pageLoad('USA');
  sleep(0.5);
}
