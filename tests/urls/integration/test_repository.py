import pytest

from url_shortener.urls.domain import model
from url_shortener.urls.service_layer.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = pytest.mark.usefixtures("mappers")


def test_saves_and_loads_a_short_url(sqlite_session_factory):
    with SqlAlchemyUnitOfWork(sqlite_session_factory) as uow:
        uow.short_urls.add(model.ShortURL("abc1234", "https://example.com/"))
        uow.commit()

    with SqlAlchemyUnitOfWork(sqlite_session_factory) as uow:
        short_url = uow.short_urls.get("abc1234")
        assert short_url is not None
        assert short_url.url == "https://example.com/"
        assert short_url.events == []
