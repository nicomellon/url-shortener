from __future__ import annotations

import secrets
import string

from url_shortener.shared.domain import Aggregate

from . import events

SHORT_CODE_LENGTH = 7
_ALPHABET = string.digits + string.ascii_letters


def new_short_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(SHORT_CODE_LENGTH))


class ShortURL(Aggregate):
    def __init__(self, short_code: str, url: str):
        super().__init__()
        self.short_code = short_code
        self.url = url

    @classmethod
    def create(cls, short_code: str, url: str) -> ShortURL:
        short_url = cls(short_code, url)
        short_url.events.append(events.ShortURLCreated(short_code=short_code, url=url))
        return short_url
