import pytest

from url_shortener.domain import model

pytestmark = pytest.mark.usefixtures("mappers")


def test_saves_and_loads_a_short_url(sqlite_session_factory):
    with sqlite_session_factory() as session:
        session.add(model.ShortURL("abc1234", "https://example.com/"))
        session.commit()

    with sqlite_session_factory() as session:
        short_url = session.get(model.ShortURL, "abc1234")
        assert short_url is not None
        assert short_url.url == "https://example.com/"
