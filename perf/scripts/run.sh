#!/usr/bin/env bash
# Run one k6 scenario end to end: seed the cache, start the API, load it,
# write the report, tear everything down.
#
#   ./perf/scripts/run.sh smoke              sanity check, ~30s
#   ./perf/scripts/run.sh load               the run that gates a release
#   ./perf/scripts/run.sh stress             find the breaking point
#   ./perf/scripts/run.sh spike              surge and recovery
#   ./perf/scripts/run.sh calculate          CPU-bound POST path
#   ./perf/scripts/run.sh abuse              what refusing a request costs
#
#   --no-prom     skip Prometheus; produce only the standalone HTML report
#   --reseed      rebuild the seeded cache even if it already exists
#   --keep-server leave gunicorn running afterwards (for manual poking)
#
#   WORKERS= / THREADS=  gunicorn's concurrency (default 4x4). Changing one
#                        and holding the scenario fixed is how a saturation
#                        ceiling is attributed to the pool or to the app.
#
# Exit code is k6's own: 0 = every SLO met, 99 = an SLO was breached.
# That exit code, not a dashboard panel, is the authoritative verdict.
set -euo pipefail

PERF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$PERF_DIR/.." && pwd)"
BACKEND_DIR="$REPO_DIR/Back-end"
VENV_PYTHON="$BACKEND_DIR/.venv/bin/python"
DB_PATH="instance/perf-seed.sqlite3"
# Deliberately not 5000. The Playwright suite starts its own Flask there
# with `reuseExistingServer: true` (Front-end/playwright.config.ts), so a
# perf server left on 5000 gets silently adopted by the E2E run -- which
# then tests the wrong database and fails in a way that looks like an app
# regression. Different port, no collision.
PORT="${PORT:-5055}"
# gunicorn's concurrency, overridable so a run can ask *why* it saturated.
# The API's throughput ceiling is set by how many requests it can have in
# flight at once; holding the load constant and changing only this
# separates "the worker pool is the ceiling" from "the application is".
# Defaults reproduce the committed baselines -- change them only for a
# deliberate comparison, and say so when reporting the numbers.
WORKERS="${WORKERS:-4}"
THREADS="${THREADS:-4}"
BASE_URL="http://127.0.0.1:$PORT"
PROM_URL="${PROM_URL:-http://localhost:9090/api/v1/write}"

SCENARIO="${1:-}"
shift || true
USE_PROM=1
RESEED=0
KEEP_SERVER=0
for arg in "$@"; do
  case "$arg" in
    --no-prom|--no-prometheus) USE_PROM=0 ;;
    --reseed) RESEED=1 ;;
    --keep-server) KEEP_SERVER=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

if [[ ! -f "$PERF_DIR/k6/$SCENARIO.js" ]]; then
  echo "usage: $0 {smoke|load|stress|spike|calculate|abuse} [--no-prom] [--reseed] [--keep-server]" >&2
  exit 2
fi

for tool in k6 curl; do
  command -v "$tool" >/dev/null || { echo "$tool is not installed" >&2; exit 1; }
done
[[ -x "$VENV_PYTHON" ]] || { echo "no virtualenv at $VENV_PYTHON -- see Back-end/README.md" >&2; exit 1; }
"$VENV_PYTHON" -c 'import gunicorn' 2>/dev/null || {
  echo "gunicorn is missing. Install it with:" >&2
  echo "  cd Back-end && .venv/bin/pip install -e '.[perf]'" >&2
  exit 1
}

# ---------------------------------------------------------------- seed --
# A load test must never depend on live provider APIs: they are slow,
# rate-limited, and would make every run measure someone else's network.
if [[ $RESEED -eq 1 || ! -f "$BACKEND_DIR/$DB_PATH" ]]; then
  echo "==> seeding $DB_PATH"
  (cd "$BACKEND_DIR" && "$VENV_PYTHON" scripts/seed_perf_db.py "$DB_PATH")
else
  echo "==> reusing $DB_PATH (--reseed to rebuild)"
fi

# --------------------------------------------------------------- serve --
# gunicorn, not `flask run`: the dev server is single-process and
# explicitly not for production use, so measuring it under concurrency
# measures the dev server rather than this API.
SERVER_PID=""
cleanup() {
  if [[ -n "$SERVER_PID" && $KEEP_SERVER -eq 0 ]]; then
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

mkdir -p "$PERF_DIR/reports"
SERVER_LOG="$PERF_DIR/reports/server.log"

if curl -sf "$BASE_URL/api/v1/health" >/dev/null 2>&1; then
  echo "==> reusing the API already listening on $PORT"
else
  echo "==> starting gunicorn on $PORT ($WORKERS workers x $THREADS threads)"
  # LOG_LEVEL=WARNING silences the per-calculation audit stream
  # (app/api/audit.py logs a JSON line for every indicator computed, which
  # is ~70 MB across a 3-minute `calculate` run). Suppressing it does not
  # take work out of the measurement: that module builds the dict and calls
  # json.dumps before the logger's level is consulted, so the serialization
  # cost stays. What it removes is synchronous local-disk I/O that only
  # exists because the load generator and the server share one box.
  #
  # What remains -- gunicorn's own warnings and any traceback -- goes to a
  # file rather than the terminal, so k6's progress stays readable.
  (
    cd "$BACKEND_DIR"
    INFLATION_DB_PATH="$DB_PATH" LOG_LEVEL=WARNING exec "$BACKEND_DIR/.venv/bin/gunicorn" \
      --workers "$WORKERS" --worker-class gthread --threads "$THREADS" \
      --bind "127.0.0.1:$PORT" --log-level warning \
      'app:create_app()'
  ) > "$SERVER_LOG" 2>&1 &
  SERVER_PID=$!

  for _ in $(seq 1 60); do
    curl -sf "$BASE_URL/api/v1/health" >/dev/null 2>&1 && break
    kill -0 "$SERVER_PID" 2>/dev/null || { echo "gunicorn exited during startup" >&2; exit 1; }
    sleep 1
  done
  curl -sf "$BASE_URL/api/v1/health" >/dev/null || { echo "API never became healthy" >&2; exit 1; }
fi

# ----------------------------------------------------------------- run --
# Timestamp first, scenario second. Grafana can only sort the run dropdown
# alphabetically, so this is what makes "newest" and "top of the list" the
# same thing -- with `scenario-timestamp`, opening the dashboard cold lands
# on whichever scenario name happens to sort last, not on the latest run.
# It orders `perf/reports/` chronologically too.
TESTID="$(date -u +%Y%m%dT%H%M%SZ)-$SCENARIO"
COMMIT="$(git -C "$REPO_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)"
REPORT="$PERF_DIR/reports/$TESTID.html"

K6_ARGS=(
  --tag "testid=$TESTID"
  --tag "scenario=$SCENARIO"
  --tag "server=gunicorn"
  --tag "pool=${WORKERS}x${THREADS}"
  --tag "commit=$COMMIT"
  --out "web-dashboard=export=$REPORT"
)

if [[ $USE_PROM -eq 1 ]]; then
  if curl -sf "${PROM_URL%/api/v1/write}/-/healthy" >/dev/null 2>&1; then
    K6_ARGS+=(--out experimental-prometheus-rw)
    export K6_PROMETHEUS_RW_SERVER_URL="$PROM_URL"
    # k6 sends only p(99) by default; the dashboard needs the full set,
    # and asking for them here is cheaper than deriving them in PromQL.
    export K6_PROMETHEUS_RW_TREND_STATS="p(50),p(90),p(95),p(99),min,max,avg"
    export K6_PROMETHEUS_RW_PUSH_INTERVAL="5s"
    # Deliberately off. Stale markers end each series cleanly when the run
    # finishes, but they also discard the final flush -- measured at ~17%
    # of requests missing from the totals on a 30s run. Prometheus is
    # started with --query.lookback-delta=15s instead, which ends the
    # series just as cleanly without losing the last batch.
    export K6_PROMETHEUS_RW_STALE_MARKERS="false"
  else
    echo "==> Prometheus is not reachable at $PROM_URL -- HTML report only"
    echo "    start it with: ./perf/scripts/stack.sh up"
    USE_PROM=0
  fi
fi

echo "==> running $SCENARIO as $TESTID"
set +e
BASE_URL="$BASE_URL" k6 run "${K6_ARGS[@]}" "$PERF_DIR/k6/$SCENARIO.js"
K6_EXIT=$?
set -e

# -------------------------------------------------------------- report --
echo
echo "==> results"
echo "    HTML report: $REPORT"
# Only when this invocation started the server -- otherwise the file on
# disk belongs to some earlier run and pointing at it would mislead.
[[ -n "$SERVER_PID" ]] && echo "    server log:  $SERVER_LOG"
if [[ $USE_PROM -eq 1 ]]; then
  echo "    Grafana:     http://localhost:3001/d/lens-qa-perf/?var-testid=$TESTID&from=now-30m&to=now"
fi
case $K6_EXIT in
  0)  echo "    verdict:     PASS -- every SLO met" ;;
  99) echo "    verdict:     FAIL -- an SLO was breached (see the thresholds above)" ;;
  *)  echo "    verdict:     ERROR -- k6 exited $K6_EXIT" ;;
esac

exit $K6_EXIT
