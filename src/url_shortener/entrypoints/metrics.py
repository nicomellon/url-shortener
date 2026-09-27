"""Prometheus metrics for the HTTP app, served at GET /metrics.

Latency is recorded as a histogram rather than as precomputed percentiles, because
percentiles can't be averaged across instances or time windows, but histogram buckets
can be summed and then turned into percentiles by Prometheus.

With several worker processes, each worker writes its metrics to files in
PROMETHEUS_MULTIPROC_DIR, and whichever worker serves /metrics adds them all up.
So every metric here must be push-based (updated by the process it describes), and
gauges declare how to combine the workers' values.
"""

import os
import threading
import time

import psutil
from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)
from sqlalchemy import Engine, event
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from url_shortener import config

REQUESTS = Counter(
    "http_requests_total",
    "HTTP requests handled",
    ["method", "handler", "status"],
)
REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Time from receiving an HTTP request to sending the whole response",
    ["method", "handler"],
    # Finer than the defaults at the low end, where a redirect service lives
    buckets=(
        0.001,
        0.0025,
        0.005,
        0.0075,
        0.01,
        0.025,
        0.05,
        0.075,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)
REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being handled",
    multiprocess_mode="livesum",
)
DB_POOL_CHECKED_OUT = Gauge(
    "db_pool_checked_out",
    "Database connections currently in use by requests",
    multiprocess_mode="livesum",
)
DB_POOL_CONNECTIONS_OPEN = Gauge(
    "db_pool_connections_open",
    "Database connections open, in use or idle",
    multiprocess_mode="livesum",
)
# "app_" rather than the standard "process_", which the Linux-only built-in
# collector already uses. One series per worker, to show how evenly load spreads.
PROCESS_CPU_SECONDS = Gauge(
    "app_process_cpu_seconds",
    "CPU time used by the API process (user + system)",
    multiprocess_mode="liveall",
)
PROCESS_MEMORY = Gauge(
    "app_process_resident_memory_bytes",
    "Resident memory of the API process",
    multiprocess_mode="liveall",
)

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    multiproc_dir = config.get_settings().prometheus_multiproc_dir
    if multiproc_dir:
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry, path=multiproc_dir)
    else:
        registry = REGISTRY
    return Response(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)


def mark_process_dead() -> None:
    """Drop this process' live gauges, so a stopped worker stops counting."""
    multiproc_dir = config.get_settings().prometheus_multiproc_dir
    if multiproc_dir:
        multiprocess.mark_process_dead(os.getpid(), multiproc_dir)


class PrometheusMiddleware:
    """Records the count, status and duration of every HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status = 500

        async def send_and_record_status(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        start = time.perf_counter()
        REQUESTS_IN_PROGRESS.inc()
        try:
            await self.app(scope, receive, send_and_record_status)
        finally:
            REQUESTS_IN_PROGRESS.dec()
            # Label by route template, not raw path: one time series per short
            # code would overwhelm Prometheus
            route = scope.get("route")
            handler = getattr(route, "path", "unmatched")
            method = scope["method"]
            REQUEST_DURATION.labels(method, handler).observe(
                time.perf_counter() - start
            )
            REQUESTS.labels(method, handler, str(status)).inc()


def register_pool_metrics(engine: Engine) -> None:
    """Track the engine's connection pool. Requests that wait for a free
    connection queue here, not in Postgres."""
    event.listen(engine, "connect", lambda *_: DB_POOL_CONNECTIONS_OPEN.inc())
    event.listen(engine, "close", lambda *_: DB_POOL_CONNECTIONS_OPEN.dec())
    event.listen(engine, "close_detached", lambda *_: DB_POOL_CONNECTIONS_OPEN.dec())
    event.listen(engine, "checkout", lambda *_: DB_POOL_CHECKED_OUT.inc())
    event.listen(engine, "checkin", lambda *_: DB_POOL_CHECKED_OUT.dec())


class ProcessSampler:
    """Samples this process' CPU and memory in a background thread. The built-in
    process collector only works on Linux; psutil also works on macOS."""

    def __init__(self, interval_seconds: float = 1.0) -> None:
        self._process = psutil.Process()
        self._interval_seconds = interval_seconds
        self._stopped = threading.Event()
        self._thread = threading.Thread(
            target=self._run, name="process-sampler", daemon=True
        )

    def sample(self) -> None:
        cpu = self._process.cpu_times()
        PROCESS_CPU_SECONDS.set(cpu.user + cpu.system)
        PROCESS_MEMORY.set(self._process.memory_info().rss)

    def start(self) -> None:
        self.sample()
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        self._thread.join()

    def _run(self) -> None:
        while not self._stopped.wait(self._interval_seconds):
            self.sample()
