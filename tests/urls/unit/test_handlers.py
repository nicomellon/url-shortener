import logging

import pytest

from url_shortener import bootstrap
from url_shortener.urls.domain import commands, model
from url_shortener.urls.service_layer import handlers, unit_of_work

from ...fakes import FakeRepository


class FakeUnitOfWork(unit_of_work.AbstractUnitOfWork):
    def __init__(self):
        self.short_urls = FakeRepository[model.ShortURL](key="short_code")
        self.committed = False

    def _commit(self):
        self.committed = True

    def rollback(self):
        pass


def bootstrap_test_app(uow: FakeUnitOfWork | None = None):
    return bootstrap.bootstrap(start_orm=False, urls_uow=uow or FakeUnitOfWork())


def test_create_short_url():
    uow = FakeUnitOfWork()
    bus = bootstrap_test_app(uow)

    bus.handle(commands.CreateShortURL("abc1234", "https://example.com/"))

    short_url = uow.short_urls.get("abc1234")
    assert short_url is not None
    assert short_url.url == "https://example.com/"
    assert uow.committed


def test_cannot_reuse_a_taken_short_code():
    uow = FakeUnitOfWork()
    bus = bootstrap_test_app(uow)
    bus.handle(commands.CreateShortURL("abc1234", "https://example.com/"))

    with pytest.raises(handlers.ShortCodeTaken):
        bus.handle(commands.CreateShortURL("abc1234", "https://other.example.com/"))

    short_url = uow.short_urls.get("abc1234")
    assert short_url is not None
    assert short_url.url == "https://example.com/"


def test_short_url_created_event_is_handled(caplog):
    bus = bootstrap_test_app()
    with caplog.at_level(logging.INFO):
        bus.handle(commands.CreateShortURL("abc1234", "https://example.com/"))

    assert "Short URL created: abc1234 -> https://example.com/" in caplog.text
