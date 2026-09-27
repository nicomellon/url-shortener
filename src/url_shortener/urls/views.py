"""Read-only queries (the "Q" in CQRS). They bypass the domain model and read
straight from the database."""

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_url(session: Session, short_code: str) -> str | None:
    return session.execute(
        text("SELECT url FROM short_urls WHERE short_code = :short_code"),
        dict(short_code=short_code),
    ).scalar_one_or_none()
