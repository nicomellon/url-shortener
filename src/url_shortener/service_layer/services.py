import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from url_shortener.domain import model

logger = logging.getLogger(__name__)


class ShortCodeTaken(Exception):
    pass


def create_short_url(session: Session, short_code: str, url: str) -> None:
    session.add(model.ShortURL(short_code, url))
    # Let the primary key catch a taken code, rather than checking first: a check
    # followed by an insert races with a concurrent request picking the same code
    try:
        session.commit()
    except IntegrityError as e:
        session.rollback()
        raise ShortCodeTaken(f"Short code {short_code} is already taken") from e
    logger.info("Short URL created: %s -> %s", short_code, url)
