from dataclasses import dataclass

from my_project.shared.domain import Event


@dataclass
class ThingCreated(Event):
    ref: str
