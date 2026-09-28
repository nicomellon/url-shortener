import pytest
from sqlalchemy import create_engine, delete, insert

from url_shortener import views
from url_shortener.adapters import cache, orm


@pytest.fixture
def read_engine(tmp_path):
    # A file database, so the engine has a real connection pool to inspect
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    orm.create_tables(engine)
    add_short_url(engine, "abc1234", "https://example.com/")
    return engine.execution_options(isolation_level="AUTOCOMMIT")


@pytest.fixture
def read_cache():
    return cache.LRUCache(maxsize=10)


def add_short_url(engine, short_code, url):
    with engine.begin() as connection:
        connection.execute(
            insert(orm.short_urls).values(short_code=short_code, url=url)
        )


def test_gets_the_url_for_a_short_code(read_engine, read_cache):
    assert views.get_url(read_engine, read_cache, "abc1234") == "https://example.com/"
    assert views.get_url(read_engine, read_cache, "unknown") is None


def test_views_return_their_connection_before_returning(read_engine, read_cache):
    views.get_url(read_engine, read_cache, "abc1234")

    assert read_engine.pool.checkedout() == 0


def test_serves_repeat_reads_from_the_cache(read_engine, read_cache):
    views.get_url(read_engine, read_cache, "abc1234")
    with read_engine.begin() as connection:
        connection.execute(delete(orm.short_urls))

    assert views.get_url(read_engine, read_cache, "abc1234") == "https://example.com/"


def test_does_not_cache_unknown_codes(read_engine, read_cache):
    assert views.get_url(read_engine, read_cache, "new1234") is None
    add_short_url(read_engine, "new1234", "https://example.com/new")

    assert (
        views.get_url(read_engine, read_cache, "new1234") == "https://example.com/new"
    )
