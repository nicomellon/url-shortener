import logging

import pytest

from url_shortener import bootstrap
from url_shortener.example.domain import commands, model
from url_shortener.example.service_layer import handlers, unit_of_work

from ...fakes import FakeRepository


class FakeUnitOfWork(unit_of_work.AbstractUnitOfWork):
    def __init__(self):
        self.things = FakeRepository[model.Thing]()
        self.committed = False

    def _commit(self):
        self.committed = True

    def rollback(self):
        pass


def bootstrap_test_app():
    return bootstrap.bootstrap(start_orm=False, example_uow=FakeUnitOfWork())


def test_create_thing():
    uow = FakeUnitOfWork()
    bus = bootstrap.bootstrap(start_orm=False, example_uow=uow)

    bus.handle(commands.CreateThing("t1", "First thing"))

    thing = uow.things.get("t1")
    assert thing is not None
    assert thing.name == "First thing"
    assert uow.committed


def test_cannot_create_a_thing_twice():
    bus = bootstrap_test_app()
    bus.handle(commands.CreateThing("t1", "First thing"))

    with pytest.raises(handlers.ThingAlreadyExists):
        bus.handle(commands.CreateThing("t1", "Another thing"))


def test_thing_created_event_is_handled(caplog):
    bus = bootstrap_test_app()
    with caplog.at_level(logging.INFO):
        bus.handle(commands.CreateThing("t1", "First thing"))

    assert "Thing created: t1" in caplog.text
