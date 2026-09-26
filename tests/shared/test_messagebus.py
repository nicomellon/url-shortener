from dataclasses import dataclass

from my_project.shared.domain import Aggregate, Command, Event
from my_project.shared.messagebus import MessageBus
from my_project.shared.unit_of_work import AbstractUnitOfWork

from ..fakes import FakeRepository
from ..random_refs import random_ref


class Widget(Aggregate):
    def __init__(self, ref: str):
        super().__init__()
        self.ref = ref
        self.events.append(WidgetCreated(ref))


@dataclass
class CreateWidget(Command):
    ref: str


@dataclass
class WidgetCreated(Event):
    ref: str


class FakeUnitOfWork(AbstractUnitOfWork):
    def __init__(self):
        self.widgets = FakeRepository[Widget]()
        self.committed = False

    def _commit(self):
        self.committed = True

    def rollback(self):
        pass


def test_command_is_handled_and_resulting_events_are_dispatched():
    uow = FakeUnitOfWork()
    seen_events: list[Event] = []

    def create_widget(cmd: CreateWidget):
        with uow:
            uow.widgets.add(Widget(cmd.ref))
            uow.commit()

    bus = MessageBus(
        uows=[uow],
        event_handlers={WidgetCreated: [seen_events.append]},
        command_handlers={CreateWidget: create_widget},
    )

    ref = random_ref()
    bus.handle(CreateWidget(ref))

    assert uow.widgets.get(ref) is not None
    assert uow.committed
    assert seen_events == [WidgetCreated(ref)]


def test_failing_event_handler_does_not_stop_other_handlers():
    seen_events: list[Event] = []

    def failing_handler(event):
        raise RuntimeError("boom")

    bus = MessageBus(
        uows=[],
        event_handlers={WidgetCreated: [failing_handler, seen_events.append]},
        command_handlers={},
    )

    bus.handle(WidgetCreated("w1"))

    assert seen_events == [WidgetCreated("w1")]
