"""Base classes for every bounded context's domain model."""


class Command:
    """A request to do something. Name commands in the imperative: CreateThing."""


class Event:
    """A fact that happened. Name events in the past tense: ThingCreated."""


class Aggregate:
    """Base class for aggregate roots.

    Aggregates record domain events in ``self.events``. The unit of work
    collects them after a handler runs and passes them to the message bus.
    """

    def __init__(self) -> None:
        self.events: list[Event] = []
