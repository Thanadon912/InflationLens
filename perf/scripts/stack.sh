#!/usr/bin/env bash
# Start or stop the results backend (Prometheus + Grafana).
#
#   ./perf/scripts/stack.sh up      start and wait until both are healthy
#   ./perf/scripts/stack.sh down    stop, keeping stored runs
#   ./perf/scripts/stack.sh wipe    stop and delete every stored run
#   ./perf/scripts/stack.sh status  show what is running
#
# Runs can also be done without any of this -- see `run.sh --no-prom`,
# which produces the standalone HTML report and nothing else.
set -euo pipefail

PERF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$PERF_DIR/docker-compose.yml")
GRAFANA_URL="http://localhost:3001"

case "${1:-up}" in
  up)
    "${COMPOSE[@]}" up -d
    printf 'waiting for prometheus and grafana'
    for _ in $(seq 1 60); do
      if curl -sf http://localhost:9090/-/healthy >/dev/null 2>&1 &&
         curl -sf "$GRAFANA_URL/api/health" >/dev/null 2>&1; then
        printf '\nready\n  Grafana:    %s\n  Prometheus: http://localhost:9090\n' "$GRAFANA_URL"
        exit 0
      fi
      printf '.'
      sleep 1
    done
    printf '\n'
    echo "stack did not become healthy in 60s; check: ${COMPOSE[*]} logs" >&2
    exit 1
    ;;
  down)
    "${COMPOSE[@]}" down
    ;;
  wipe)
    "${COMPOSE[@]}" down -v
    echo "stored runs deleted"
    ;;
  status)
    "${COMPOSE[@]}" ps
    ;;
  *)
    echo "usage: $0 {up|down|wipe|status}" >&2
    exit 2
    ;;
esac
