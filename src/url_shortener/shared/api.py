"""FastAPI dependencies shared by every context's routes."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from url_shortener.shared.messagebus import MessageBus


def get_bus(request: Request) -> MessageBus:
    return request.app.state.bus


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


Bus = Annotated[MessageBus, Depends(get_bus)]
DbSession = Annotated[Session, Depends(get_session)]
