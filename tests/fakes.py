from typing import Any

from url_shortener.shared.domain import Aggregate
from url_shortener.shared.repository import AbstractRepository


class FakeRepository[T: Aggregate](AbstractRepository[T]):
    """In-memory repository that finds aggregates by their ``key`` attribute."""

    def __init__(self, aggregates: list[T] | None = None, key: str = "ref"):
        super().__init__()
        self._aggregates = set(aggregates or [])
        self._key = key

    def _add(self, aggregate):
        self._aggregates.add(aggregate)

    def _get(self, identifier: Any):
        return next(
            (a for a in self._aggregates if getattr(a, self._key) == identifier), None
        )
