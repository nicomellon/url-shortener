import os

# Tests supply their own config rather than reading a developer's .env
os.environ["DATABASE_URL"] = "sqlite://"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import clear_mappers, sessionmaker  # noqa: E402

from url_shortener import bootstrap, config  # noqa: E402
from url_shortener.entrypoints.fastapi_app import app  # noqa: E402


@pytest.fixture
def in_memory_sqlite_db():
    engine = create_engine("sqlite:///:memory:")
    bootstrap.create_tables(engine)
    return engine


@pytest.fixture
def sqlite_session_factory(in_memory_sqlite_db):
    yield sessionmaker(bind=in_memory_sqlite_db)


@pytest.fixture
def mappers():
    bootstrap.start_mappers()
    yield
    clear_mappers()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The whole app, running against a fresh SQLite database file."""
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    config.get_settings.cache_clear()
    bootstrap.create_tables(create_engine(database_url))
    with TestClient(app) as client:
        yield client
    config.get_settings.cache_clear()
