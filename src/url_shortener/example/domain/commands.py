from dataclasses import dataclass

from url_shortener.shared.domain import Command


@dataclass
class CreateThing(Command):
    ref: str
    name: str
