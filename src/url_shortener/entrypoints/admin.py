"""One-off admin tasks, run in the same environment as the app.

See https://12factor.net/admin-processes. Usage:

    url-shortener-admin init-db
    url-shortener-admin seed-urls --count 10000000
"""

import argparse
import logging
import string
import time

from sqlalchemy import Engine, create_engine, insert
from sqlalchemy.dialects import postgresql, sqlite

from url_shortener import config
from url_shortener.adapters import orm

logger = logging.getLogger(__name__)

SEED_CODE_LENGTH = 7
# Must match loadtest/lib.js, which computes the same codes to read them back
SEED_CODE_ALPHABET = string.digits + string.ascii_letters
SEED_BATCH_SIZE = 10_000


def init_db(args: argparse.Namespace) -> None:
    logger.info("Creating database tables")
    engine = create_engine(config.get_settings().database_url)
    orm.create_tables(engine)


def seed_short_code(index: int) -> str:
    """The short code of the ``index``-th seeded URL: ``index`` in base 62,
    zero-padded, so a load test can compute valid codes without listing them."""
    code = ""
    for _ in range(SEED_CODE_LENGTH):
        index, digit = divmod(index, len(SEED_CODE_ALPHABET))
        code = SEED_CODE_ALPHABET[digit] + code
    return code


def seed_url(index: int) -> str:
    # Roughly the length of a real long URL, so rows take a realistic amount of space
    return f"https://example.com/2026/09/an-article-title-{index}?utm_source=seed"


def seed_urls(args: argparse.Namespace) -> None:
    """Bulk-insert URLs for load tests, bypassing the domain for speed. Safe to
    re-run: rows that already exist are skipped."""
    engine = create_engine(config.get_settings().database_url)
    orm.create_tables(engine)
    statement = _insert_ignoring_duplicates(engine)
    logger.info("Seeding %d URLs", args.count)
    start = time.perf_counter()
    with engine.connect() as connection:
        for batch_start in range(0, args.count, SEED_BATCH_SIZE):
            batch_end = min(batch_start + SEED_BATCH_SIZE, args.count)
            connection.execute(
                statement,
                [
                    {"short_code": seed_short_code(i), "url": seed_url(i)}
                    for i in range(batch_start, batch_end)
                ],
            )
            connection.commit()
            if batch_end % 1_000_000 == 0 or batch_end == args.count:
                logger.info("Seeded %d/%d URLs", batch_end, args.count)
    logger.info("Seeding took %.1fs", time.perf_counter() - start)


def _insert_ignoring_duplicates(engine: Engine):
    table = orm.short_urls
    match engine.dialect.name:
        case "postgresql":
            return postgresql.insert(table).on_conflict_do_nothing()
        case "sqlite":
            return sqlite.insert(table).on_conflict_do_nothing()
        case _:
            return insert(table)


def main():
    parser = argparse.ArgumentParser(prog="url-shortener-admin")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init-db", help="create database tables").set_defaults(
        func=init_db
    )

    seed = subparsers.add_parser("seed-urls", help="bulk-insert URLs for load tests")
    seed.add_argument("--count", type=int, default=1_000_000)
    seed.set_defaults(func=seed_urls)

    args = parser.parse_args()
    config.configure_logging()
    args.func(args)
