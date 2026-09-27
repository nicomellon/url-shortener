from dataclasses import dataclass

from url_shortener.shared.domain import Event


@dataclass
class ShortURLCreated(Event):
    short_code: str
    url: str
