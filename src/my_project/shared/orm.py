from sqlalchemy import create_engine, event
from sqlalchemy.orm import registry, sessionmaker

from my_project import config
from my_project.shared.domain import Aggregate

# One registry for all contexts, so table names must be unique across contexts
mapper_registry = registry()
metadata = mapper_registry.metadata


def default_session_factory() -> sessionmaker:
    return sessionmaker(bind=create_engine(config.get_settings().database_url))


@event.listens_for(Aggregate, "load", propagate=True)
def receive_load(aggregate, _):
    # The ORM does not call __init__ when loading objects from the database
    aggregate.events = []
