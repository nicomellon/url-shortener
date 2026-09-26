from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from my_project.example.domain import commands, events, model
from my_project.shared.domain import Command, Event

if TYPE_CHECKING:
    from . import unit_of_work

logger = logging.getLogger(__name__)


class ThingAlreadyExists(Exception):
    pass


def create_thing(
    cmd: commands.CreateThing,
    uow: unit_of_work.AbstractUnitOfWork,
):
    with uow:
        if uow.things.get(cmd.ref) is not None:
            raise ThingAlreadyExists(f"Thing {cmd.ref} already exists")
        uow.things.add(model.Thing.create(cmd.ref, cmd.name))
        uow.commit()


def log_thing_created(event: events.ThingCreated):
    logger.info("Thing created: %s", event.ref)


COMMAND_HANDLERS: dict[type[Command], Callable] = {
    commands.CreateThing: create_thing,
}

EVENT_HANDLERS: dict[type[Event], list[Callable]] = {
    events.ThingCreated: [log_thing_created],
}
