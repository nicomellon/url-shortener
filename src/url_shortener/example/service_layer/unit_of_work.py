from sqlalchemy.orm import Session

from url_shortener.example.domain import model
from url_shortener.shared import repository
from url_shortener.shared import unit_of_work as shared_unit_of_work


class AbstractUnitOfWork(shared_unit_of_work.AbstractUnitOfWork):
    things: repository.AbstractRepository[model.Thing]


class SqlAlchemyUnitOfWork(
    shared_unit_of_work.SqlAlchemyUnitOfWork, AbstractUnitOfWork
):
    def _create_repositories(self, session: Session) -> None:
        self.things = repository.SqlAlchemyRepository(session, model.Thing)
