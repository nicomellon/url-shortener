from dataclasses import dataclass

from my_project.shared.domain import Command


@dataclass
class CreateThing(Command):
    ref: str
    name: str
