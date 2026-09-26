from __future__ import annotations

from my_project.shared.domain import Aggregate

from . import events


class Thing(Aggregate):
    def __init__(self, ref: str, name: str):
        super().__init__()
        self.ref = ref
        self.name = name

    @classmethod
    def create(cls, ref: str, name: str) -> Thing:
        thing = cls(ref, name)
        thing.events.append(events.ThingCreated(ref=ref))
        return thing
