from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from prometheus_client import REGISTRY
from sqlalchemy.orm import clear_mappers

from url_shortener import config
from url_shortener.adapters import orm
from url_shortener.entrypoints import api, metrics


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config.configure_logging()
    orm.start_mappers()
    session_factory = orm.default_session_factory()
    app.state.session_factory = session_factory
    pool_collector = metrics.ConnectionPoolCollector(session_factory.kw["bind"])
    REGISTRY.register(pool_collector)
    yield
    REGISTRY.unregister(pool_collector)
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
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_config=None,
        access_log=settings.access_log,
    )
