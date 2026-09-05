/* Service level objectives for the Inflation Lens API.
 *
 * Two sets of numbers live here, because k6 and the Grafana dashboard do
 * not measure the same thing and pretending they do would make one of
 * them lie:
 *
 *   SLO       -- what k6 enforces. A single percentile blended across
 *                every endpoint of that kind, over the whole run.
 *   PANEL_SLO -- what the dashboard colours against. The *worst single
 *                endpoint's* percentile, because Prometheus stores one
 *                series per endpoint and percentiles cannot be
 *                recombined into a blended one after the fact.
 *
 * On the same clean baseline run those two differ by roughly 5x for the
 * read path (blended p95 9.5 ms, worst endpoint 46 ms), so one shared
 * constant would either fail every healthy run in Grafana or be too
 * slack to catch anything in k6. Both are useful: the blended figure
 * catches the API getting broadly slower, the worst-endpoint figure
 * catches one endpoint going bad while the average hides it.
 *
 * Both are whole-run figures. k6's Prometheus remote-write output does
 * not send a percentile *per flush*: outside native-histogram mode it
 * accumulates every sample from the start of the run and pushes the
 * run-to-date aggregate every interval. Verified on a spike run --
 * `_min` never rose and `_max` froze at 1512.7 ms for the whole
 * recovery, which only a cumulative series does.
 *
 * The consequence is worth knowing before reading a graph: these series
 * ratchet. A time series built from them shows the run-to-date
 * percentile, not latency at that moment, so it can show a regression
 * appearing but *cannot* show one clearing. Read recovery from
 * throughput at a fixed VU count instead -- see "Reading the dashboard"
 * in ../../README.md.
 *
 * k6's exit code (0 pass / 99 breach) comes from `SLO` and is the
 * authoritative verdict. `PANEL_SLO` is documentation of what is baked
 * into grafana/dashboards/qa-performance.json -- Grafana cannot import
 * JavaScript, so those values are duplicated there and the two must be
 * changed together. See "Changing an SLO" in ../../README.md.
 *
 * Calibration: measured on gunicorn (4 workers x 4 threads) against the
 * seeded cache -- a 20-VU 4m30s `load` run for the read path, and a
 * 200 req/s 3-minute `calculate` run for the POST path -- then given
 * roughly 2-3x headroom so ordinary machine noise does not fail a run.
 * Re-derive both sets on markedly different hardware.
 */

/* Enforced by k6. Milliseconds. */
export const SLO = {
  // GET endpoints: read a pre-calculated snapshot out of the SQLite cache
  // and serialize it. No engine work happens on this path.
  // Baseline: blended p95 9.5 ms, p99 ~13 ms.
  read: { p95: 25, p99: 60 },

  // POST endpoints: run a calculation engine over the request body, so
  // they are CPU-bound. Baseline: blended p95 15 ms sustained at 200
  // req/s for three minutes with zero failures -- the engines are not
  // where this API struggles.
  calc: { p95: 40, p99: 120 },

  // Applies to every request in a run, regardless of kind.
  errorRate: 0.01, // under 1% of requests may fail
  checkRate: 0.99, // over 99% of content assertions must pass
};

/* Mirrored in the dashboard JSON, in SECONDS there (k6 states durations in
 * milliseconds; the Prometheus remote-write output reports them in
 * seconds). Worst endpoint, over the whole run.
 *
 * Baselines: read 46 ms p95 / 49 ms p99, both from GET /world/cross-section,
 * the widest payload. calc 23 ms p95 / 33 ms p99, both from
 * POST /global/dashboard, the heaviest engine path. */
export const PANEL_SLO = {
  read: { p95: 100, p99: 150 },
  calc: { p95: 60, p99: 120 },
};

/* The threshold block every scenario spreads into its options. Kept here
 * so a new scenario cannot ship without SLOs attached. */
export function thresholds() {
  return {
    http_req_failed: [`rate<${SLO.errorRate}`],
    checks: [`rate>${SLO.checkRate}`],
    'http_req_duration{kind:read}': [`p(95)<${SLO.read.p95}`, `p(99)<${SLO.read.p99}`],
    'http_req_duration{kind:calc}': [`p(95)<${SLO.calc.p95}`, `p(99)<${SLO.calc.p99}`],
  };
}
