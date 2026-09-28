"""FastAPI dependencies for the routes."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy import Engine
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    # A session per request: sessions aren't thread-safe, and FastAPI runs sync
    # routes in a thread pool. The session factory and engine are safe to share.
    # A session only takes a connection on its first query, inside the route.
    with request.app.state.session_factory() as session:
        yield session


async def get_read_engine(request: Request) -> Engine:
    # async: no thread-pool hop just to fetch a shared object. Views take their own
    # connection from it, only for as long as their query runs.
    return request.app.state.read_engine


DbSession = Annotated[Session, Depends(get_session)]
ReadEngine = Annotated[Engine, Depends(get_read_engine)]
