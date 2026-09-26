import pytest
from sqlalchemy import text

from url_shortener.shared.unit_of_work import SqlAlchemyUnitOfWork


@pytest.fixture
def session_factory(sqlite_session_factory):
    session = sqlite_session_factory()
    session.execute(text("CREATE TABLE widgets (ref VARCHAR(255) PRIMARY KEY)"))
    session.commit()
    return sqlite_session_factory


def insert_widget(session, ref):
    session.execute(text("INSERT INTO widgets (ref) VALUES (:ref)"), dict(ref=ref))


def get_refs(session_factory):
    return [r for [r] in session_factory().execute(text("SELECT ref FROM widgets"))]


def test_commits_work(session_factory):
    uow = SqlAlchemyUnitOfWork(session_factory)
    with uow:
        insert_widget(uow.session, "widget1")
        uow.commit()

    assert get_refs(session_factory) == ["widget1"]


def test_rolls_back_uncommitted_work_by_default(session_factory):
    uow = SqlAlchemyUnitOfWork(session_factory)
    with uow:
        insert_widget(uow.session, "widget1")

    assert get_refs(session_factory) == []


def test_rolls_back_on_error(session_factory):
    class MyException(Exception):
        pass

    uow = SqlAlchemyUnitOfWork(session_factory)
    with pytest.raises(MyException), uow:
        insert_widget(uow.session, "widget1")
        raise MyException()

    assert get_refs(session_factory) == []
