from dataclasses import dataclass

from url_shortener.shared.domain import Event


@dataclass
class ThingCreated(Event):
    ref: str
