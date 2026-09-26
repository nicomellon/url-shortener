from __future__ import annotations

import abc
from collections.abc import Iterator

from sqlalchemy.orm import Session, sessionmaker

from url_shortener.shared import repository
from url_shortener.shared.domain import Event


class AbstractUnitOfWork(abc.ABC):
    """Transaction boundary. Each bounded context subclasses this and declares
    one repository attribute per aggregate."""

    def __enter__(self) -> AbstractUnitOfWork:
        return self

    def __exit__(self, *args):
        self.rollback()

    def commit(self):
        self._commit()

    def collect_new_events(self) -> Iterator[Event]:
        for repo in self._repositories():
            for aggregate in repo.seen:
                while aggregate.events:
                    yield aggregate.events.pop(0)

    def _repositories(self) -> list[repository.AbstractRepository]:
        return [
            value
            for value in vars(self).values()
            if isinstance(value, repository.AbstractRepository)
        ]

    @abc.abstractmethod
    def _commit(self):
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self):
        raise NotImplementedError


class SqlAlchemyUnitOfWork(AbstractUnitOfWork):
    def __init__(self, session_factory: sessionmaker):
        self.session_factory = session_factory

    def __enter__(self):
        self.session: Session = self.session_factory()
        self._create_repositories(self.session)
        return super().__enter__()

    def __exit__(self, *args):
        super().__exit__(*args)
        self.session.close()

    def _create_repositories(self, session: Session) -> None:
        """Override to create the context's repositories for this session."""

    def _commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()
