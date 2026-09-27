from dataclasses import dataclass

from url_shortener.shared.domain import Command


@dataclass
class CreateShortURL(Command):
    short_code: str
    url: str
