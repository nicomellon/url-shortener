import pytest
from sqlalchemy import create_engine, insert

from url_shortener import views
from url_shortener.adapters import orm


@pytest.fixture
def read_engine(tmp_path):
    # A file database, so the engine has a real connection pool to inspect
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    orm.create_tables(engine)
    with engine.begin() as connection:
        connection.execute(
            insert(orm.short_urls).values(
                short_code="abc1234", url="https://example.com/"
            )
        )
    return engine.execution_options(isolation_level="AUTOCOMMIT")


def test_gets_the_url_for_a_short_code(read_engine):
    assert views.get_url(read_engine, "abc1234") == "https://example.com/"
    assert views.get_url(read_engine, "unknown") is None


def test_views_return_their_connection_before_returning(read_engine):
    views.get_url(read_engine, "abc1234")

    assert read_engine.pool.checkedout() == 0
