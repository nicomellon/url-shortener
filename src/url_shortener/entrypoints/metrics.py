"""Prometheus metrics for the HTTP app, served at GET /metrics.

Latency is recorded as a histogram rather than as precomputed percentiles, because
percentiles can't be averaged across instances or time windows, but histogram buckets
can be summed and then turned into percentiles by Prometheus.
"""

import time
from collections.abc import Iterator

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from sqlalchemy import Engine
from sqlalchemy.pool import QueuePool
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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
    "http_requests_in_progress", "HTTP requests currently being handled"
)

router = APIRouter()


@router.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


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


class ConnectionPoolCollector(Collector):
    """Reports how busy the SQLAlchemy connection pool is when scraped. Requests
    that wait for a free connection queue here, not in Postgres."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def collect(self) -> Iterator[GaugeMetricFamily]:
        pool = self.engine.pool
        if not isinstance(pool, QueuePool):
            return
        yield GaugeMetricFamily(
            "db_pool_size", "Connections the pool keeps open", value=pool.size()
        )
        yield GaugeMetricFamily(
            "db_pool_checked_out",
            "Connections currently in use by requests",
            value=pool.checkedout(),
        )
        yield GaugeMetricFamily(
            "db_pool_overflow",
            "Connections open beyond the pool size",
            value=max(pool.overflow(), 0),
        )
