from typing import Any
from datetime import datetime, timezone

from app.api.models.otp import Otp
from app.api.schemas.auth import AuthBase
from app.api.repo.base import BaseRepository


class OtpRepository(BaseRepository[AuthBase, Otp]):
    model = Otp

    def _entity_to_model(self, entity: AuthBase) -> model:
        return Otp(**entity.model_dump())

    def _get_filters(self, **filters) -> list[Any]:
        filter_conditions = []

        if "otp" in filters:
            filter_conditions.append(self.model.otp == filters["otp"])
        if "user_id" in filters:
            filter_conditions.append(self.model.user_id == filters["user_id"])
        if "status" in filters:
            filter_conditions.append(self.model.status == filters["status"])
        if "expires_at" in filters:
            filter_conditions.append(self.model.expires_at > datetime.now(timezone.utc))

        return filter_conditions

    def _get_sort_fields(self, sort: str) -> list[Any]:
        pass
