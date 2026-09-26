import pytest

from my_project.example.domain.model import Thing
from my_project.example.service_layer.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.usefixtures("mappers")


def test_saves_and_loads_a_thing(sqlite_session_factory):
    with SqlAlchemyUnitOfWork(sqlite_session_factory) as uow:
        uow.things.add(Thing("t1", "First thing"))
        uow.commit()

    with SqlAlchemyUnitOfWork(sqlite_session_factory) as uow:
        thing = uow.things.get("t1")
        assert thing is not None
        assert thing.name == "First thing"
        assert thing.events == []
