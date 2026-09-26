import abc
from typing import Any

from sqlalchemy.orm import Session

from url_shortener.shared.domain import Aggregate


class AbstractRepository[T: Aggregate](abc.ABC):
    def __init__(self):
        self.seen: set[T] = set()

    def add(self, aggregate: T):
        self._add(aggregate)
        self.seen.add(aggregate)

    def get(self, identifier: Any) -> T | None:
        aggregate = self._get(identifier)
        if aggregate:
            self.seen.add(aggregate)
        return aggregate

    @abc.abstractmethod
    def _add(self, aggregate: T):
        raise NotImplementedError

    @abc.abstractmethod
    def _get(self, identifier: Any) -> T | None:
        raise NotImplementedError


class SqlAlchemyRepository[T: Aggregate](AbstractRepository[T]):
    def __init__(self, session: Session, aggregate_class: type[T]):
        super().__init__()
        self.session = session
        self.aggregate_class = aggregate_class

    def _add(self, aggregate):
        self.session.add(aggregate)

    def _get(self, identifier):
        return self.session.get(self.aggregate_class, identifier)
