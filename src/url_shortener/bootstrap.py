"""Composition root: the only module that knows about every bounded context.

To add a context, import its orm, handlers and unit of work below, then add it to
``start_mappers`` and ``bootstrap``.
"""

import inspect
from collections import defaultdict
from collections.abc import Callable

from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from url_shortener.shared import messagebus, orm
from url_shortener.shared.domain import Command, Event
from url_shortener.urls.adapters import orm as urls_orm
from url_shortener.urls.service_layer import handlers as urls_handlers
from url_shortener.urls.service_layer import unit_of_work as urls_unit_of_work


def bootstrap(
    start_orm: bool = True,
    session_factory: sessionmaker | None = None,
    urls_uow: urls_unit_of_work.AbstractUnitOfWork | None = None,
) -> messagebus.MessageBus:
    if session_factory is None:
        session_factory = orm.default_session_factory()
    if urls_uow is None:
        urls_uow = urls_unit_of_work.SqlAlchemyUnitOfWork(session_factory)

    if start_orm:
        start_mappers()

    # One entry per context: its handlers, and the dependencies they can ask for
    # by parameter name. Add adapters (notifications, publishers, ...) here too.
    contexts = [
        (urls_handlers, {"uow": urls_uow}),
    ]

    command_handlers: dict[type[Command], Callable] = {}
    event_handlers: dict[type[Event], list[Callable]] = defaultdict(list)
    for context_handlers, dependencies in contexts:
        for command_type, handler in context_handlers.COMMAND_HANDLERS.items():
            command_handlers[command_type] = inject_dependencies(handler, dependencies)
        for event_type, handlers in context_handlers.EVENT_HANDLERS.items():
            event_handlers[event_type].extend(
                inject_dependencies(handler, dependencies) for handler in handlers
            )

    return messagebus.MessageBus(
        uows=[urls_uow],
        event_handlers=dict(event_handlers),
        command_handlers=command_handlers,
    )


def start_mappers():
    urls_orm.start_mappers()


def create_tables(engine: Engine):
    """Create every context's tables. Importing their orm modules registers them."""
    orm.metadata.create_all(engine)


def inject_dependencies(handler, dependencies):
    params = inspect.signature(handler).parameters
    deps = {
        name: dependency for name, dependency in dependencies.items() if name in params
    }
    return lambda message: handler(message, **deps)
