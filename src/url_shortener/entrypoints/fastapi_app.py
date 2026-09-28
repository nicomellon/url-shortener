import atexit
import os
import shutil
import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from sqlalchemy.orm import clear_mappers

from url_shortener import config
from url_shortener.adapters import orm
from url_shortener.entrypoints import api, metrics


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config.configure_logging()
    orm.start_mappers()
    session_factory = orm.default_session_factory()
    engine = session_factory.kw["bind"]
    metrics.register_pool_metrics(engine)
    app.state.session_factory = session_factory
    # Shares the engine's pool: same connections, just used in autocommit mode
    app.state.read_engine = engine.execution_options(isolation_level="AUTOCOMMIT")
    process_sampler = metrics.ProcessSampler()
    process_sampler.start()
    yield
    process_sampler.stop()
    engine.dispose()
    metrics.mark_process_dead()
    clear_mappers()


app = FastAPI(lifespan=lifespan)
app.add_middleware(metrics.PrometheusMiddleware)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(metrics.router)
# Last, because its catch-all GET /{short_code} would shadow routes added after it
app.include_router(api.router)


def main():
    """Serve the app, binding to $PORT (https://12factor.net/port-binding)."""
    settings = config.get_settings()
    if settings.web_concurrency > 1:
        _share_metrics_between_workers()
    uvicorn.run(
        # An import string, so each worker process can import the app itself
        "url_shortener.entrypoints.fastapi_app:app",
        host=settings.host,
        port=settings.port,
        workers=settings.web_concurrency,
        log_config=None,
        access_log=settings.access_log,
    )


def _share_metrics_between_workers() -> None:
    # A scratch directory for prometheus_client's per-worker files, not app state:
    # it's recreated empty on every start
    directory = tempfile.mkdtemp(prefix="url-shortener-metrics-")
    atexit.register(shutil.rmtree, directory, ignore_errors=True)
    # prometheus_client reads this when imported, so it must be set before uvicorn
    # spawns the workers, which inherit it. config.Settings reads it back.
    os.environ["PROMETHEUS_MULTIPROC_DIR"] = directory
