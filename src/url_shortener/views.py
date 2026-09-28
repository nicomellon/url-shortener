"""Read-only queries (the "Q" in CQRS). They bypass the domain model and read
straight from the database.

Views take the autocommit read engine, so a single query is a single statement with
no BEGIN/ROLLBACK around it. That's safe because one statement always sees one
consistent snapshot. A view that runs several queries which must agree with each
other needs a transaction (``with engine.begin() as connection:``), or it can see a
mix of before and after a concurrent write (read skew).

Views hold a connection only while their query runs. Taking one earlier, while the
request still waits for a thread to run on, can deadlock: requests hold every
connection waiting for a thread, while every thread waits for a connection.
"""

from sqlalchemy import Engine, text

from url_shortener.adapters import cache


def get_url(engine: Engine, read_cache: cache.LRUCache, short_code: str) -> str | None:
    # Short URLs never change and are never deleted, so a cached URL can't go
    # stale. Unknown codes aren't cached: one may be created a moment later.
    url = read_cache.get(short_code)
    if url is not None:
        return url
    with engine.connect() as connection:
        url = connection.execute(
            text("SELECT url FROM short_urls WHERE short_code = :short_code"),
            dict(short_code=short_code),
        ).scalar_one_or_none()
    if url is not None:
        read_cache.put(short_code, url)
    return url
