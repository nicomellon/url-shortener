from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from sqlalchemy.orm import clear_mappers

from url_shortener import bootstrap, config
from url_shortener.example.entrypoints import api as example_api
from url_shortener.shared import orm


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config.configure_logging()
    session_factory = orm.default_session_factory()
    app.state.session_factory = session_factory
    app.state.bus = bootstrap.bootstrap(session_factory=session_factory)
    yield
    clear_mappers()


app = FastAPI(lifespan=lifespan)
app.include_router(example_api.router)


@app.get("/health")
def health():
    return {"status": "ok"}


def main():
    """Serve the app, binding to $PORT (https://12factor.net/port-binding)."""
    settings = config.get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port, log_config=None)
