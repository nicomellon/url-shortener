"""Read-only queries (the "Q" in CQRS). They bypass the domain model and read
straight from the database."""

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_thing(session: Session, ref: str) -> dict[str, Any] | None:
    row = session.execute(
        text("SELECT ref, name FROM things WHERE ref = :ref"), dict(ref=ref)
    ).first()
    return dict(row._mapping) if row else None
