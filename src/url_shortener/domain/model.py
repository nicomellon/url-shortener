import secrets
import string

SHORT_CODE_LENGTH = 7
_ALPHABET = string.digits + string.ascii_letters


def new_short_code() -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(SHORT_CODE_LENGTH))


class ShortURL:
    def __init__(self, short_code: str, url: str):
        self.short_code = short_code
        self.url = url
