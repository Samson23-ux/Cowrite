from typing import Any
from sqlalchemy import and_

from app.api.models.user import User
from app.api.schemas.user import UserBase
from app.api.repo.base import BaseRepository


class UserRepository(BaseRepository[UserBase, User]):
    model = User

    @staticmethod
    def _entity_to_model(entity: UserBase) -> model:
        return User(**entity.model_dump())

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "email" in filters:
            filter_conditions.append(self.model.email == filters["email"])
        if "google_email" in filters:
            filter_conditions.append(self.model.google_email == filters["google_email"])
        if "is_active" in filters:
            filter_conditions.append(self.model.is_active.is_(filters["is_active"]))
        if "is_verified" in filters:
            filter_conditions.append(self.model.is_verified.is_(filters["is_verified"]))

        return filter_conditions

    def _get_sort_fields(self, sort: str) -> list[Any]:
        sortable_fields: dict = {"created_at": self.model.created_at}
        return [sortable_fields.get(sort, self.model.created_at)]
