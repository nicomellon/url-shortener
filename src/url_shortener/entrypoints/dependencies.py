"""FastAPI dependencies for the routes."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session


def get_session(request: Request) -> Iterator[Session]:
    # A session per request: sessions aren't thread-safe, and FastAPI runs sync
    # routes in a thread pool. The session factory and engine are safe to share.
    with request.app.state.session_factory() as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]
