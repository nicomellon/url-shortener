from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from url_shortener.shared.domain import Command, Event
from url_shortener.urls.domain import commands, events, model

if TYPE_CHECKING:
    from . import unit_of_work

logger = logging.getLogger(__name__)


class ShortCodeTaken(Exception):
    pass


def create_short_url(
    cmd: commands.CreateShortURL,
    uow: unit_of_work.AbstractUnitOfWork,
):
    with uow:
        if uow.short_urls.get(cmd.short_code) is not None:
            raise ShortCodeTaken(f"Short code {cmd.short_code} is already taken")
        uow.short_urls.add(model.ShortURL.create(cmd.short_code, cmd.url))
        uow.commit()


def log_short_url_created(event: events.ShortURLCreated):
    logger.info("Short URL created: %s -> %s", event.short_code, event.url)


COMMAND_HANDLERS: dict[type[Command], Callable] = {
    commands.CreateShortURL: create_short_url,
}

EVENT_HANDLERS: dict[type[Event], list[Callable]] = {
    events.ShortURLCreated: [log_short_url_created],
}
