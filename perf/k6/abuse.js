/* Abuse: what it costs the API to say no.
 *
 * Every other scenario in this directory sends requests the API is meant
 * to answer. That leaves the entire refusal path unmeasured -- and the
 * refusal path is the one hostile traffic drives. The question here is
 * not "does it return the right error", which the backend's own suite
 * already covers, but "does returning that error cost more than serving
 * real data".
 *
 * It matters because of two facts about this API taken together. It has
 * no rate limiting (README.md: open by design), and its throughput
 * ceiling is a fixed gunicorn worker pool -- so anything that makes a
 * request more expensive than a normal one is an amplifier: fewer
 * requests are needed to fill the pool. If a 404 costs the same as a page
 * load, a flood of 404s is no worse than a flood of traffic. If it costs
 * ten times more, it is ten times cheaper to attack with.
 *
 * The run answers it by comparing like with like. Each iteration sends a
 * real page load *and* a refused request, so `{kind:read}` and
 * `{kind:reject}` are measured on the same machine, in the same seconds,
 * against the same worker pool. Comparing a rejection here against the
 * read baseline from a separate `load` run would fold in every difference
 * between the two runs.
 *
 * Held at 20 VUs on purpose -- the same steady state as `load`, and well
 * under the ~70 VU saturation knee that `stress` found. Past that knee
 * every endpoint converges on the same queue-dominated p95 (see "It
 * saturates, it does not fall over" in ../README.md), which would make
 * the two kinds look identical no matter what they really cost. The
 * comparison is only meaningful below saturation.
 */

import { sleep } from 'k6';

import { thresholds } from './lib/slo.js';
import { pageLoad, cachedIndicator, malformedRequest, oversizedBody } from './lib/journey.js';

/* How often an iteration sends the oversized body instead of a small
 * malformed one. Overridable because it is the variable worth isolating:
 * `OVERSIZE_RATE=0` reruns everything else unchanged, which separates
 * "small refusals are costly" from "the 2 MiB case is costly" -- two
 * findings with completely different consequences. */
const OVERSIZE_RATE = Number(__ENV.OVERSIZE_RATE ?? 0.1);

/* What each iteration sends after its page load. This is the scenario's
 * independent variable, and the reason it is a knob rather than a
 * hardcoded choice: a difference in read latency is only attributable to
 * abusive traffic if the alternative was measured on the same harness, at
 * the same VU count and think time, on the same box.
 *
 *   reject  (default) a refused request -- the measurement
 *   valid             a valid single GET instead. The control that
 *                     matters most: it holds the request *count* and
 *                     shape identical and changes only whether the extra
 *                     request is refused, so a difference cannot be
 *                     blamed on there simply being a sixth request.
 *   none              nothing -- the page load alone, which is what
 *                     `load` measures, at this scenario's think time.
 */
const TAIL = __ENV.TAIL || 'reject';

export const options = {
  scenarios: {
    abuse: {
      // Ramped in, not started cold. `load` reaches its 20 VUs over a
      // minute, and matching that is not cosmetic: starting 20 VUs at
      // once puts 120 simultaneous requests against a 16-thread pool in
      // the first instant, and the handful of ~300 ms outliers that
      // produces is enough to set p99 over a run this short while leaving
      // p95 untouched. Measured cold-started: read p95 10.79 ms (healthy,
      // matching the baseline) but p99 133.9 ms against `load`'s 13.87 ms.
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: Number(__ENV.VUS || 20) },
        { duration: '2m', target: Number(__ENV.VUS || 20) },
      ],
      gracefulRampDown: '15s',
    },
  },
  thresholds: thresholds(),
};

export default function () {
  // The control: a valid batch, identical to what `load` sends -- same
  // 80/20 geography mix included. The mix is not cosmetic: an all-USA
  // batch requests /regions/us and /categories/USA on every single
  // iteration, and measured that way the read p99 blows out to ~93-144 ms
  // against `load`'s 13.87 ms *with no refusals involved at all*. Copying
  // the baseline's mix exactly is what makes this run's read numbers
  // comparable to it, and therefore what makes a difference in them
  // attributable to the refusals.
  pageLoad(Math.random() < 0.8 ? 'USA' : 'EA');

  if (TAIL === 'valid') {
    cachedIndicator('USA');
  } else if (TAIL !== 'none') {
    // The oversized case is weighted down to one iteration in ten. It is
    // the only case that moves real bytes -- 2 MiB per request -- and at
    // an even weight the run would spend most of its time measuring
    // loopback throughput between the load generator and the server,
    // which share one box.
    if (Math.random() < OVERSIZE_RATE) {
      oversizedBody();
    } else {
      malformedRequest();
    }
  }

  sleep(Math.random() * 2 + 0.5); // 0.5-2.5s, identical to load.js
}
