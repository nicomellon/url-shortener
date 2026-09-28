#!/usr/bin/env bash
# Benchmarks the API at several worker counts: for each one, starts the API, runs
# ramp.js against it, stops it, then prints a per-step summary (loadtest/analyze.py).
#
#   loadtest/bench.sh 1 2 4 8
#
# Needs Postgres and Prometheus running (make stack-up), port 8000 free, and a local
# k6. Ramp shape and pool size come from the environment (see the Makefile).
# Results go to loadtest/results/<timestamp>/.
set -uo pipefail

workers=("${@:-1}")
dir=$(cd "$(dirname "$0")" && pwd)
out="$dir/results/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$out"
cd "$dir/.."

export ACCESS_LOG=false
export DB_POOL_SIZE=${DB_POOL_SIZE:-5} DB_MAX_OVERFLOW=${DB_MAX_OVERFLOW:-5}
export MAX_READ_RATE=${MAX_READ_RATE:-8000} STEPS=${STEPS:-8} STEP_SECONDS=${STEP_SECONDS:-15}
WRITE_RATE=${WRITE_RATE:-100}
SEED_COUNT=${SEED_COUNT:-1000000}
printf 'MAX_READ_RATE=%s\nSTEPS=%s\nSTEP_SECONDS=%s\n' \
  "$MAX_READ_RATE" "$STEPS" "$STEP_SECONDS" > "$out/params"

if curl -sf localhost:8000/health >/dev/null; then
  echo "Something is already serving on port 8000; stop it first" >&2
  exit 1
fi

# Postgres CPU (inside the Docker VM) and this machine's CPU by process group,
# sampled every few seconds, for analyze.py
db=$(docker compose ps -q db)
( while true; do
    echo "$(date +%s) $(docker stats --no-stream --format '{{.CPUPerc}}' "$db")"
    sleep 3
  done ) > "$out/db-cpu.txt" &
db_sampler=$!
( while true; do
    ps -A -o %cpu=,comm= | awk -v t="$(date +%s)" '
      {c+=$1} /k6$/{k+=$1} /[Pp]ython/{p+=$1} /limactl|vz|Virtualization/{v+=$1}
      END {printf "%s total=%.0f k6=%.0f python=%.0f vm=%.0f\n", t, c, k, p, v}'
    sleep 3
  done ) > "$out/host-cpu.txt" &
host_sampler=$!
trap 'kill $db_sampler $host_sampler 2>/dev/null' EXIT

for w in "${workers[@]}"; do
  echo "== $w worker(s)"
  WEB_CONCURRENCY=$w uv run url-shortener-api > "$out/api-$w.log" 2>&1 &
  api=$!
  for _ in $(seq 60); do
    curl -sf localhost:8000/health >/dev/null && break
    sleep 1
  done
  if ! curl -sf localhost:8000/health >/dev/null; then
    echo "API didn't start; see $out/api-$w.log" >&2
    kill $api 2>/dev/null
    exit 1
  fi
  sleep 2

  echo "$w $(date +%s)" >> "$out/starts.txt"
  loadtest/run.sh ramp -e MAX_READ_RATE="$MAX_READ_RATE" -e STEPS="$STEPS" \
    -e STEP_SECONDS="$STEP_SECONDS" -e WRITE_RATE="$WRITE_RATE" \
    -e SEED_COUNT="$SEED_COUNT" > "$out/k6-$w.txt" 2>&1

  kill -TERM $api
  for _ in $(seq 20); do kill -0 $api 2>/dev/null || break; sleep 1; done
  if kill -0 $api 2>/dev/null; then
    echo "API didn't stop within 20s; killing it" | tee -a "$out/errors.txt"
    pkill -9 -f url-shortener-api
  fi
  wait $api 2>/dev/null
  sleep 10 # let Postgres and the machine settle between runs
done

python3 "$dir/analyze.py" "$out"
echo "Results in $out"
