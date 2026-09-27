#!/usr/bin/env bash
# Runs a load test and sends k6's client-side metrics to Prometheus, so Grafana can
# show them next to the API's own metrics.
#
#   loadtest/run.sh steady [-e READ_RATE=2000 -e SEED_COUNT=10000000 ...]
#   loadtest/run.sh ramp   [-e MAX_READ_RATE=8000 ...]
#
# Uses a local k6 if there is one (brew install k6), otherwise the k6 Docker image.
# Prefer a local k6: in Docker, k6 competes with Postgres for the Docker VM's CPUs.
set -euo pipefail

script=${1:?usage: loadtest/run.sh <steady|ramp> [k6 options]}
shift
dir=$(cd "$(dirname "$0")" && pwd)

if command -v k6 >/dev/null; then
  K6_PROMETHEUS_RW_SERVER_URL=http://localhost:9090/api/v1/write \
  K6_PROMETHEUS_RW_TREND_STATS="p(50),p(95),p(99),max" \
    k6 run -o experimental-prometheus-rw "$@" "$dir/$script.js"
else
  echo "k6 not found locally; running it in Docker" >&2
  docker run --rm -i \
    --add-host=host.docker.internal:host-gateway \
    -v "$dir:/scripts:ro" \
    -e BASE_URL="${BASE_URL:-http://host.docker.internal:8000}" \
    -e K6_PROMETHEUS_RW_SERVER_URL=http://host.docker.internal:9090/api/v1/write \
    -e K6_PROMETHEUS_RW_TREND_STATS="p(50),p(95),p(99),max" \
    grafana/k6 run -o experimental-prometheus-rw "$@" "/scripts/$script.js"
fi
