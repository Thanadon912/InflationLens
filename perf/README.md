# Performance testing

Load tests for the Inflation Lens API, written in [k6](https://k6.io), with
results in a Grafana dashboard built for QA rather than for engineers.

The backend's own suite covers correctness — 700+ tests, 97% branch coverage,
plus a Playwright end-to-end run. None of it measures *time*. This directory
answers the questions that suite cannot: how fast is the API under load, where
does it break, and which endpoint is responsible.

---

## Quick start

```bash
# once: install gunicorn into the backend virtualenv
cd Back-end && .venv/bin/pip install -e '.[perf]' && cd ..

# start the results backend (Prometheus + Grafana)
./perf/scripts/stack.sh up

# run a test
./perf/scripts/run.sh smoke     # 30s sanity check -- always run this first
./perf/scripts/run.sh load      # 4.5min, the run that says "healthy or not"
```

`run.sh` prints an HTML report path and a Grafana link when it finishes. Open
either. Grafana needs no login.

Nothing else has to be running: `run.sh` seeds its own database, starts its own
API, and stops it again afterwards.

---

## The scenarios

| Command | Takes | Answers |
|---|---|---|
| `run.sh smoke` | 30s | Is the harness sound? Server up, cache seeded, every request contract still valid. Run before anything else. |
| `run.sh load` | 4.5m | Does the API meet its SLOs under expected traffic — 20 concurrent users on the workbench? **This is the run that gates a release.** |
| `run.sh stress` | 9m | Where does it break? Steps 20 → 200 users until latency gives way. Measured: throughput tops out at **~700 req/s around 70 users**; beyond that, latency alone degrades. |
| `run.sh spike` | 4m | Does it recover? Jumps to 200 users for 30s, then watches the two minutes after. Measured: **yes, immediately.** |
| `run.sh calculate` | 3m | How much can the calculation engines take? Drives the POST endpoints at a fixed arrival rate — 200/s by default, `RATE=400 ./perf/scripts/run.sh calculate` to push further. |
| `run.sh abuse` | 2.5m | What does it cost to say *no*? Mixes refused requests — 404s, schema errors, malformed JSON, bodies over the 2 MiB cap — into a normal page-load stream. Measured: refusing costs about **a tenth** of serving. |

Options: `--no-prom` (HTML report only, no Docker needed), `--reseed` (rebuild
the test database), `--keep-server` (leave gunicorn up afterwards).

`abuse` takes three of its own, all there to make it a controlled experiment
rather than a single number: `TAIL=` chooses what follows each page load
(`reject`, the default; `valid` for an ordinary request instead; `none` for the
page load alone), `OVERSIZE_RATE=` how often the refused request is the 2 MiB
one (default `0.1`), and `VUS=` the user count (default `20`). `TAIL=valid` is
the control that matters — it holds the request count and shape identical and
changes only whether the extra request is refused.

`WORKERS=` and `THREADS=` set gunicorn's concurrency (default `4` and `4`).
Holding a scenario fixed and changing only these is how a throughput ceiling
gets attributed to the worker pool or to the application —
`WORKERS=8 ./perf/scripts/run.sh spike` is the comparison run. Anything other
than the default makes a run incomparable to the committed baselines, so say
which pool you used when reporting numbers; the dashboard records it as a
`pool` tag.

**A `FAIL` on `stress` or `spike` is the expected result**, not a regression —
those runs exist to push the API past its ceiling, and both breach the latency
SLO by design. Read the curve, not the verdict tile. `load` and `abuse` are the
scenarios whose verdicts mean something: both are calibrated to run below
saturation and both are expected to pass.

---

## Reading the dashboard

<http://localhost:3001> — pick a run from the **Test run** dropdown at the top
left. Runs are named `<UTC timestamp>-scenario`, so the list is newest-first and
opens on the run you just finished.

The page is four sections, in the order a result is normally read.

### 1 · Verdict — did this run pass?

Five tiles. If **SLO status** is green and **Checks passed** is 100%, the run
was clean and there is nothing else to look at.

- **SLO status** — PASS/FAIL against every SLO at once. Deliberately strict: it
  holds the *worst single endpoint* to the budget rather than the average
  across all of them, so one bad endpoint cannot hide behind many fast ones.
  The authoritative verdict is k6's exit code, which `run.sh` prints as
  `verdict: PASS` / `verdict: FAIL`.
- **Error rate** — requests that failed or returned an unexpected status.
- **Slowest read p95** — the worst p95 among the GET endpoints, not the blended
  average across all of them, which would hide one slow endpoint behind many
  fast ones.
- **Total requests** — a much smaller number than usual means the run ended early.
- **Checks passed** — *content* assertions, not status codes. Below 100% means a
  response was structurally wrong even though it returned 200.

### 2 · During the run — how it behaved over time

- **Response time by path** — `read` (GET, served from the cache) and `calc`
  (POST, running a calculation engine) are drawn separately because their SLOs
  differ by a factor of ten.

  **Read this line as cumulative, not instantaneous.** Outside
  native-histogram mode, k6's Prometheus output accumulates every sample from
  the start of the run and pushes the run-to-date percentile each interval, so
  the series only ever ratchets: it shows a slowdown *arriving*, and then holds
  that level even after the API has fully recovered. A line that climbs and
  stays up is worth reporting — but a line that stays up after the load drops
  is not evidence of anything. **To judge recovery, use throughput instead:**
  compare requests/sec in the quiet tail against the quiet head at the same VU
  count. Equal throughput at equal VUs means equal latency, whatever this panel
  is still showing. (`spike` is the run where this matters — see the table
  further down.)
- **Failures** — failed requests per second by status code. `HTTP 0` is k6's
  code for a request that never got a response at all — a timeout or refused
  connection, which is a different bug from a 500.
- **Load applied vs. throughput delivered** — the saturation panel. While the
  API keeps up, virtual users and requests/sec rise together. The point where
  users keep climbing and throughput flattens is the API's ceiling.

### 3 · Where it hurts — which endpoint to open a bug against

The **By endpoint** table is where a bug report comes from. One row per
endpoint, worst first.

**SLO budget** is the column to read: each endpoint's p95 as a share of the SLO
it is actually held to. That puts the fast GETs and the slow POSTs on one
comparable scale — under 100% is within budget, over 100% broke it. The bar
gauge beside it is the same number, drawn.

### 4 · Run context

**Failing checks** lists content assertions that did not hold. Empty is healthy
— a row here is a correctness bug, not a performance one. **What was run**
records the scenario, the server, the commit, and how hard it pushed.

---

## What is actually being tested

The `load` scenario reproduces what `Front-end/data.js` really does: five GETs
fired in parallel on every page load and every geography or window change.
Hitting one endpoint at a time would understate the concurrent pressure on the
SQLite cache, which is the thing most likely to give way.

Every request is checked on its **content**, not just its status:

- `/measures/USA` returns all seven published measures with values
- `/regions/us` returns four census regions and 50+ inherited states
- `/world/cross-section` covers more than 100 economies
- `POST .../dashboard` computes every indicator, none `unavailable`

This matters because a misconfigured or unseeded cache still answers `200` — with
an empty payload, faster than a real one. Checking only the status code would
report that as an excellent result.

**Only `abuse` sends requests the API should refuse.** Every other scenario
sends exclusively well-formed traffic, which leaves the entire rejection path —
the one hostile traffic drives — unmeasured. Its cases are asserted on the
structured error envelope from `app/api/errors.py`, not merely on status code:
a stack trace, an empty body or a proxy error page would all arrive with the
right status and the wrong contents.

**The API is served by gunicorn**, not `flask run`. Flask's development server
is explicitly not built for concurrency; measuring it under load would measure
the dev server rather than this API.

**The database is seeded, never synced.** `Back-end/scripts/seed_perf_db.py`
builds a deterministic cache at the volume `flask data sync` really produces —
7 measures × 24 months, 4 census regions, ~220 economies in the cross-section —
so payload sizes are realistic and two runs are comparable. No provider is ever
called.

---

## What the first baselines found

Measured on gunicorn (4 workers × 4 threads) against the seeded cache, on one
developer machine. Reproduce with `./perf/scripts/run.sh load` and
`./perf/scripts/run.sh calculate`.

| Run | Result |
|---|---|
| `load` — 20 VUs, 4m30s | 17,869 requests, **0 failures**, 47,648 checks all passing. Blended read p95 **9.5 ms**. |
| `calculate` — 200 req/s, 3m | 36,002 requests, **0 failures**. Blended calc p95 **15 ms**, and k6 needed at most **4 VUs** to sustain the rate. |
| `stress` — 0→200 VUs, 9m | 303,343 requests, **0 failures**, 831,456 checks all passing. Throughput ceiling **~700 req/s**, reached at **~70 VUs**. Read p95 **49 ms → 1,327 ms** past that point. |
| `spike` — 5→200→5 VUs, 3m50s | 44,077 requests, **0 failures**. Surge absorbed at **789 req/s**; **recovery is immediate** — the quiet tail delivers 56–58 req/s against a 57–59 req/s opening baseline. |
| `abuse` — 20 VUs, 2.5m | 9,948 requests, **0 failures**, 26,645 checks all passing. Refused requests cost **p95 1.18 ms** against the same run's read **p95 10.04 ms**. |

Five things worth recording:

**The calculation engines are not the bottleneck.** 200 requests/second of real
engine work — including `POST /global/dashboard`, which computes all eight
global indicators over a 225 KB body — ran for three minutes without a single
failure and without k6 having to allocate more than four VUs. The engines are
comfortably faster than the rate they were driven at.

**The widest read is the slowest.** `GET /world/cross-section` is consistently
the worst endpoint (p95 46 ms against the next-worst 36 ms). It iterates every
economy in the cross-section and computes a median, so it scales with the
number of countries in the cache rather than being a fixed-cost lookup.

**It saturates, it does not fall over.** Across every run above — 200 concurrent
users, 1.3-second responses — the API returned **zero** failed requests and
**100%** passing content checks. Nothing 500s, nothing times out, no connection
is refused. Past its ceiling this API queues; it does not shed load or corrupt
its answers. That is a materially different failure mode from one that starts
erroring, and it is why the per-endpoint error column stays empty even on the
runs that "failed": what breaches the SLO is latency alone.

**The ceiling is the worker pool, not the database.** Holding `spike` fixed and
changing only gunicorn's concurrency:

| Pool | Surge throughput | Read p95 | Max | Failed |
|---|---|---|---|---|
| 2 × 4 | 424 req/s | 1,930 ms | 2,521 ms | 0 |
| 4 × 4 *(default)* | 789 req/s | 1,267 ms | 1,513 ms | 0 |
| 8 × 4 | **1,479 req/s** | **310 ms** | 393 ms | 0 |

Throughput scales **near-linearly** with workers — 212, 197 and 185 req/s per
worker respectively, the mild decay being ordinary contention on a 12-core box
that is also running the load generator. A lock inside the application or the
SQLite cache would show the opposite: adding workers would buy nothing. So the
committed 4 × 4 is a *configuration* limit, and raising it is the first lever if
this API ever needs more headroom. Reproduce with
`WORKERS=8 ./perf/scripts/run.sh spike`.

Two corroborating details: under saturation every endpoint converges on the same
p95 — a one-row `/meta/data-sources` lookup (1,249 ms) is as slow as
`/world/cross-section`, which iterates ~220 economies (1,294 ms) — which means
the time is spent *waiting for a worker*, not doing the work. And `GET /health`
degrades in lockstep with everything else, so the queue is in front of the
application, not inside any one handler.

**Refusing a request is cheap, and refused traffic is not an amplifier.** This
is the question `abuse` exists to answer, and it matters because the API has no
rate limiting (README.md: open by design) and a fixed worker pool: anything
that costs more to refuse than to serve would let an attacker fill that pool
with less effort than a real user does. It does not. Every refusal is cheaper
than every read, in the same run and the same seconds:

| Request | p95 | Server think time (p95) |
|---|---|---|
| `GET /measures/{geo}` | 12.64 ms | 12.50 ms |
| `GET /world/cross-section` | 11.60 ms | 11.50 ms |
| *— refusals below —* | | |
| `POST …` body over 2 MiB → 413 | 1.79 ms | **0.91 ms** |
| `GET /measures/{geo}?window=…` → 400 | 1.34 ms | 1.26 ms |
| `POST …` malformed JSON → 400 | 1.33 ms | 1.25 ms |
| `GET /measures/ZZZ` → 404 | 1.25 ms | 1.17 ms |

Measured uncontended too, one request at a time: refusals take 0.5–0.8 ms
against 1.7–4.4 ms for reads. The 2 MiB case is the one to look at twice — its
*duration* is the highest of the refusals because the client has to push the
bytes, but its **think time is the lowest of all**, which is precisely what
`MAX_CONTENT_LENGTH` in `app/factory.py` is for: the body is rejected on its
declared length, before anything parses it.

The control is what makes this a finding rather than a coincidence.
`TAIL=valid ./perf/scripts/run.sh abuse` reruns the identical harness — same
VUs, same think time, same page load — with an ordinary request substituted for
the refused one. Read p95 lands at **9.64 ms** against the refusal run's
**10.04 ms**, a 4% difference on a measurement that varies by more than that
between runs. Swapping abuse in for legitimate traffic buys an attacker
nothing.

None of which makes `abuse` a security test. It measures the *cost* of a
refusal, not the API's ability to survive someone determined to send them: with
no rate limiting in front of it, one client can still occupy the whole worker
pool, exactly as `stress` shows a client can with valid traffic. The finding is
narrower and still worth having — bad traffic is no cheaper to attack with than
good traffic, so the ceiling `stress` measured is the ceiling either way.

Three things this deliberately does **not** establish. The scenarios are read-heavy
by construction, so the root `README.md`'s caution about SQLite under concurrent
**write** load is untested here, not refuted — writes happen during
`flask data sync`, which no scenario exercises. Nothing here measures an
endurance run either: the longest is nine minutes, which cannot surface a memory
or file-descriptor leak, and no scenario starts against a cold cache. And
`GET /regions/us` is an
unexplained outlier (run p95 301 ms while its peers sit above 1,100 ms, despite
identical request counts in the same batch); it is recorded rather than
explained, and is worth a look before anyone leans on per-endpoint numbers from
a saturated run.

---

## Changing an SLO

All the numbers are declared in **`k6/lib/slo.js`**, in two sets — because k6
and Grafana genuinely measure different things:

| | `SLO` | `PANEL_SLO` |
|---|---|---|
| Measures | one percentile **blended across every endpoint**, over the whole run | the **worst single endpoint**, over the whole run |
| Used by | k6's thresholds → the exit code → the verdict | the dashboard's colours |
| Read p95 — baseline → budget | 9.5 ms → 25 ms | 46 ms → 100 ms |
| Calc p95 — baseline → budget | 15 ms → 40 ms | 23 ms → 60 ms |

They are ~5× apart, so a single shared number would either turn every healthy
run red in Grafana or be too slack to catch anything in k6. Both are worth
having: the blended figure catches the API getting broadly slower, the
worst-endpoint figure catches one endpoint going bad while the average hides it.

**`SLO` decides pass/fail.** k6 exits 99 on a breach; `run.sh` prints that as
`verdict: FAIL`. `PANEL_SLO` only colours panels.

Grafana cannot import a JavaScript file, so `PANEL_SLO`'s values are duplicated
in the dashboard JSON and the two must be changed together:

| | `k6/lib/slo.js` | `grafana/dashboards/qa-performance.json` |
|---|---|---|
| Units | **milliseconds** (`p95: 100`) | **seconds** (`"value": 0.1`) |
| Where | `PANEL_SLO.read` / `.calc` | `thresholds.steps` on the p95 tile, the `Error %` and `SLO budget` columns, the bar gauge divisor, and the `SLO status` expression |

The unit difference is not a mistake: k6 states durations in milliseconds and
reports them over remote write in seconds.

After editing the JSON, Grafana reloads it within ten seconds — no restart.

---

## Calibrating

The committed budgets came from a 20-VU, 4m30s `load` run against gunicorn
(4 workers × 4 threads) on the seeded cache, with 2–3× headroom so ordinary
machine noise does not fail a run. On markedly different hardware, re-derive
them:

```bash
./perf/scripts/run.sh load
# SLO       <- the run's own `{ kind:read }` / `{ kind:calc }` p95 and p99 lines
# PANEL_SLO <- the "Slowest read p95" tile and the By endpoint table
# edit both sets in k6/lib/slo.js and the dashboard thresholds, then confirm:
./perf/scripts/run.sh load     # must be PASS
```

### Proving the failure path still works

Worth doing after any change to the SLOs or the dashboard: a verdict that can
only ever say PASS is decorative. The two mechanisms are independent, so test
them separately and revert each afterwards.

**k6's verdict** — set `SLO.read.p95 = 1` in `slo.js`, run `./perf/scripts/run.sh
smoke`. It must print `✗ 'p(95)<1'` and `verdict: FAIL`.

**The dashboard's verdict** — `SLO` does not feed Grafana, so the step above
leaves the tile green. Set the p95 tile's threshold in
`grafana/dashboards/qa-performance.json` to `0.001` instead (and the same value
in the `SLO status` expression), wait ten seconds for the reload, and re-open
the dashboard. The **SLO status** tile must go red and read FAIL, and
**Slowest read p95** must turn red with it while the untouched tiles stay green.

---

## Troubleshooting

**`gunicorn is missing`** — `cd Back-end && .venv/bin/pip install -e '.[perf]'`

**`Prometheus is not reachable`** — `./perf/scripts/stack.sh up`. The run
continues either way and still writes its HTML report.

**Dashboard says "No data"** — check the **Test run** dropdown actually has your
run selected, and that the time range covers it (`Last 30 minutes` is the
default). Prometheus keeps 15 days.

**Port already in use** — the ports are chosen to stay clear of everything
else: Grafana on 3001 (3000 is the front end's static server), the API under
test on 5055 (5000 is the Playwright suite's, and it adopts whatever is already
listening there). Override with `PORT=5056 ./perf/scripts/run.sh load`.

**Everything is suspiciously fast** — check **Checks passed** is 100%. An
unseeded cache returns empty payloads at great speed.

---

## Files

```
perf/
  docker-compose.yml           Prometheus + Grafana
  prometheus/prometheus.yml
  grafana/
    provisioning/              datasource + dashboard wiring, applied at startup
    dashboards/
      qa-performance.json      the dashboard
  k6/
    lib/slo.js                 SLO numbers -- the source of truth for pass/fail
    lib/config.js              base URL, request tagging, content assertions
    lib/journey.js             the front end's real request pattern
    lib/payloads.js            valid POST bodies, built from the published contract
    smoke.js load.js stress.js spike.js calculate.js
  scripts/
    run.sh                     seed -> serve -> load -> report -> tear down
    stack.sh                   up / down / wipe / status
  reports/                     HTML reports (gitignored)
```
