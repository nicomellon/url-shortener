from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING

from url_shortener.shared.domain import Command, Event

if TYPE_CHECKING:
    from url_shortener.shared.unit_of_work import AbstractUnitOfWork

logger = logging.getLogger(__name__)

type Message = Command | Event


class MessageBus:
    def __init__(
        self,
        uows: Sequence[AbstractUnitOfWork],
        event_handlers: dict[type[Event], list[Callable]],
        command_handlers: dict[type[Command], Callable],
    ):
        self.uows = uows
        self.event_handlers = event_handlers
        self.command_handlers = command_handlers

    def handle(self, message: Message):
        self.queue = [message]
        while self.queue:
            message = self.queue.pop(0)
            if isinstance(message, Event):
                self.handle_event(message)
            elif isinstance(message, Command):
                self.handle_command(message)
            else:
                raise Exception(f"{message} was not an Event or Command")

    def handle_event(self, event: Event):
        for handler in self.event_handlers.get(type(event), []):
            try:
                logger.debug("handling event %s with handler %s", event, handler)
                handler(event)
                self._collect_new_events()
            except Exception:
                logger.exception("Exception handling event %s", event)
                continue

    def handle_command(self, command: Command):
        logger.debug("handling command %s", command)
        try:
            handler = self.command_handlers[type(command)]
            handler(command)
            self._collect_new_events()
        except Exception:
            logger.exception("Exception handling command %s", command)
            raise

    def _collect_new_events(self):
        for uow in self.uows:
            self.queue.extend(uow.collect_new_events())
