"""Summarizes a loadtest/bench.sh run: one row per worker count and ramp step.

    python3 loadtest/analyze.py loadtest/results/<timestamp>

Reads the API, k6 and Postgres metrics for each step's hold period from Prometheus,
plus the CPU samples bench.sh recorded. Standard library only.
"""

import json
import math
import sys
import urllib.parse
import urllib.request
from pathlib import Path

PROMETHEUS = "http://localhost:9090/api/v1/query_range?"
RAMP_SECONDS = 10  # matches ramp.js
READS = 'handler="/{short_code}"'
QUERIES = {
    "rps": f"sum(rate(http_requests_total{{{READS}}}[10s]))",
    "p50": "histogram_quantile(0.5, sum by (le) "
    f"(rate(http_request_duration_seconds_bucket{{{READS}}}[10s])))",
    "p99": "histogram_quantile(0.99, sum by (le) "
    f"(rate(http_request_duration_seconds_bucket{{{READS}}}[10s])))",
    # TESTID selects this run's k6 series: Prometheus keeps returning a series for
    # 5 minutes after it stops, so the previous run's would leak into this one
    "k6_p99": 'max(k6_http_req_duration_p99{name="GET /{short_code}",TESTID})',
    # "or vector(0)": k6 only creates these series once something drops or fails
    "dropped": "sum(rate(k6_dropped_iterations_total{TESTID}[10s])) or vector(0)",
    # From the request counter: k6's http_req_failed gauge has one series per
    # status, which can't be averaged into a rate
    "failed": 'sum(rate(k6_http_reqs_total{expected_response="false",TESTID}[10s]))'
    " / sum(rate(k6_http_reqs_total{TESTID}[10s])) or vector(0)",
    "api_cores": "sum(rate(app_process_cpu_seconds[10s]))",
    "pool": "sum(db_pool_checked_out)",
    # NaN (shown as nan) when the cache is off: nothing is looked up
    "hit": 'sum(rate(read_cache_lookups_total{result="hit"}[10s])) '
    "/ sum(rate(read_cache_lookups_total[10s]))",
}


def prometheus_avg(query: str, start: int, end: int) -> float:
    params = urllib.parse.urlencode(dict(query=query, start=start, end=end, step=2))
    with urllib.request.urlopen(PROMETHEUS + params) as response:
        result = json.load(response)["data"]["result"]
    values = [
        float(v) for r in result for _, v in r["values"] if not math.isinf(float(v))
    ]
    values = [v for v in values if not math.isnan(v)]
    return sum(values) / len(values) if values else math.nan


def samples_avg(path: Path, start: int, end: int, column: int) -> float:
    values = []
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) > column and start <= int(fields[0]) <= end:
            values.append(float(fields[column].split("=")[-1].rstrip("%")))
    return sum(values) / len(values) if values else math.nan


def main(out: Path) -> None:
    params = dict(line.split("=") for line in (out / "params").read_text().split())
    max_rate, steps = int(params["MAX_READ_RATE"]), int(params["STEPS"])
    hold = int(params["STEP_SECONDS"])
    print(" ".join(f"{k}={v}" for k, v in params.items()))

    # API and DB µs/req: CPU time per request, which shows an improvement even
    # below saturation, where latency barely moves. k6%: the load generator's
    # share of this machine; when host% nears 100 it measures the Mac, not the app.
    print(
        f"{'workers':>7} {'target':>6} {'reads/s':>7} {'p50':>8} {'p99':>8} "
        f"{'k6 p99':>8} {'drop/s':>6} {'fail%':>5} {'API cpu':>7} {'API µs':>6} "
        f"{'pool':>4} {'DB cpu%':>7} {'DB µs':>5} {'hit%':>5} {'k6%':>4} {'host%':>5}"
    )
    for line in (out / "starts.txt").read_text().splitlines():
        workers, started = line.split()
        for step in range(1, steps + 1):
            # Skip the first seconds of each hold, while rates settle
            hold_end = int(started) + 1 + step * (RAMP_SECONDS + hold)
            start, end = hold_end - hold + 4, hold_end - 1
            # bench.sh tags each k6 run; older runs have no testid
            testid = f'testid=~"({out.name}-{workers})?"'
            r = {
                name: prometheus_avg(q.replace("TESTID", testid), start, end)
                for name, q in QUERIES.items()
            }
            db_cpu = samples_avg(out / "db-cpu.txt", start, end, 1)
            host_cpu = samples_avg(out / "host-cpu.txt", start, end, 1)
            k6_cpu = samples_avg(out / "host-cpu.txt", start, end, 2)
            api_us = r["api_cores"] / r["rps"] * 1e6
            db_us = db_cpu / 100 / r["rps"] * 1e6
            hit = r["hit"] * 100
            print(
                f"{workers:>7} {round(max_rate * step / steps):>6} {r['rps']:>7.0f} "
                f"{r['p50'] * 1000:>6.1f}ms {r['p99'] * 1000:>6.1f}ms "
                f"{r['k6_p99'] * 1000:>6.0f}ms {r['dropped']:>6.0f} "
                f"{r['failed'] * 100:>5.1f} {r['api_cores']:>7.2f} {api_us:>6.0f} "
                f"{r['pool']:>4.0f} {db_cpu:>7.0f} {db_us:>5.0f} {hit:>5.0f} "
                f"{k6_cpu:>4.0f} {host_cpu:>5.0f}"
            )
        print()


if __name__ == "__main__":
    main(Path(sys.argv[1]))
