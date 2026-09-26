from sqlalchemy import Column, String, Table

from my_project.example.domain import model
from my_project.shared.orm import mapper_registry, metadata

things = Table(
    "things",
    metadata,
    Column("ref", String(255), primary_key=True),
    Column("name", String(255), nullable=False),
)


def start_mappers():
    mapper_registry.map_imperatively(model.Thing, things)
