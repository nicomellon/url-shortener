from sqlalchemy.orm import Session

from url_shortener.shared import repository
from url_shortener.shared import unit_of_work as shared_unit_of_work
from url_shortener.urls.domain import model


class AbstractUnitOfWork(shared_unit_of_work.AbstractUnitOfWork):
    short_urls: repository.AbstractRepository[model.ShortURL]


class SqlAlchemyUnitOfWork(
    shared_unit_of_work.SqlAlchemyUnitOfWork, AbstractUnitOfWork
):
    def _create_repositories(self, session: Session) -> None:
        self.short_urls = repository.SqlAlchemyRepository(session, model.ShortURL)
