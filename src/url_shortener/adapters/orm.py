from sqlalchemy import Column, Engine, String, Table, Text, create_engine
from sqlalchemy.orm import registry, sessionmaker

from url_shortener import config
from url_shortener.domain import model

mapper_registry = registry()
metadata = mapper_registry.metadata

short_urls = Table(
    "short_urls",
    metadata,
    Column("short_code", String(16), primary_key=True),
    Column("url", Text, nullable=False),
)


def start_mappers():
    mapper_registry.map_imperatively(model.ShortURL, short_urls)


def create_tables(engine: Engine):
    metadata.create_all(engine)


def default_session_factory() -> sessionmaker:
    return sessionmaker(bind=create_engine(config.get_settings().database_url))
