from typing import Any

from app.api.models.email import Email
from app.api.schemas.email import EmailBase
from app.api.repo.base import BaseRepository


class EmailRepository(BaseRepository[EmailBase, Email]):
    model = Email

    def _entity_to_model(self, entity: EmailBase) -> Email:
        return Email(**entity.model_dump())

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "id" in filters:
            filter_conditions.append(self.model.id == filters["id"])
        return filter_conditions
