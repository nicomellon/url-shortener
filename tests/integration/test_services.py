import logging

import pytest

from url_shortener.domain import model
from url_shortener.service_layer import services

pytestmark = pytest.mark.usefixtures("mappers")


def test_create_short_url(sqlite_session_factory):
    with sqlite_session_factory() as session:
        services.create_short_url(session, "abc1234", "https://example.com/")

    with sqlite_session_factory() as session:
        short_url = session.get(model.ShortURL, "abc1234")
        assert short_url is not None
        assert short_url.url == "https://example.com/"


def test_cannot_reuse_a_taken_short_code(sqlite_session_factory):
    with sqlite_session_factory() as session:
        services.create_short_url(session, "abc1234", "https://example.com/")

        with pytest.raises(services.ShortCodeTaken):
            services.create_short_url(session, "abc1234", "https://other.example.com/")

    with sqlite_session_factory() as session:
        short_url = session.get(model.ShortURL, "abc1234")
        assert short_url is not None
        assert short_url.url == "https://example.com/"


def test_the_session_is_usable_after_a_taken_short_code(sqlite_session_factory):
    with sqlite_session_factory() as session:
        services.create_short_url(session, "abc1234", "https://example.com/")
        with pytest.raises(services.ShortCodeTaken):
            services.create_short_url(session, "abc1234", "https://other.example.com/")

        services.create_short_url(session, "def5678", "https://other.example.com/")

        assert session.get(model.ShortURL, "def5678") is not None


def test_creating_a_short_url_is_logged(sqlite_session_factory, caplog):
    with sqlite_session_factory() as session, caplog.at_level(logging.INFO):
        services.create_short_url(session, "abc1234", "https://example.com/")

    assert "Short URL created: abc1234 -> https://example.com/" in caplog.text
