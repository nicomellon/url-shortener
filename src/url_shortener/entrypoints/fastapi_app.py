from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from sqlalchemy.orm import clear_mappers

from url_shortener import bootstrap, config
from url_shortener.shared import orm
from url_shortener.urls.entrypoints import api as urls_api


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config.configure_logging()
    session_factory = orm.default_session_factory()
    app.state.session_factory = session_factory
    app.state.bus = bootstrap.bootstrap(session_factory=session_factory)
    yield
    clear_mappers()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}


# Last, because its catch-all GET /{short_code} would shadow routes added after it
app.include_router(urls_api.router)


def main():
    """Serve the app, binding to $PORT (https://12factor.net/port-binding)."""
    settings = config.get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port, log_config=None)
