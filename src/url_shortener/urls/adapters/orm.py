from sqlalchemy import Column, String, Table, Text

from url_shortener.shared.orm import mapper_registry, metadata
from url_shortener.urls.domain import model

short_urls = Table(
    "short_urls",
    metadata,
    Column("short_code", String(16), primary_key=True),
    Column("url", Text, nullable=False),
)


def start_mappers():
    mapper_registry.map_imperatively(model.ShortURL, short_urls)
