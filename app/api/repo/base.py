from datetime import datetime
from pydantic import BaseModel
from sqlalchemy import Sequence
from sqlalchemy.orm import Session
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession
from typing import TypeVar, Generic, Any, Optional
from sqlalchemy import select, Sequence, desc, asc, update

from app.api.models.base import Base
from app.core.security import Security

SECURITY = Security()
Entity = TypeVar("Entity", bound=BaseModel)
SqlalchemyModel = TypeVar("SqlAlchemyModel", bound=Base)


class BaseRepository(ABC, Generic[Entity, SqlalchemyModel]):
    def __init__(
        self, async_session: AsyncSession = None, sync_session: Session = None
    ):
        self._sync_session = sync_session
        self._async_session = async_session

    model: type[SqlalchemyModel]

    def add(
        self, entity: Optional[Entity] = None, model: Optional[SqlalchemyModel] = None
    ):
        if not model:
            model: SqlalchemyModel = self._entity_to_model(entity)
        self._async_session.add(model)

    async def flush(self):
        await self._async_session.flush()

    async def refresh(self, model: SqlalchemyModel):
        await self._async_session.refresh(model)

    async def commit(self):
        await self._async_session.commit()

    async def rollback(self):
        await self._async_session.rollback()

    async def aclose(self):
        await self._async_session.aclose()

    async def delete(self, model: SqlalchemyModel):
        await self._async_session.delete(model)
        await self._async_session.flush()

    async def get_records(
        self,
        sort: str,
        order: str,
        cursor: str,
        limit: int,
        **filters,
    ) -> dict:
        filter_conditions: list[Any] = self._get_filters(**filters)
        sort_fields: list[Any] = self._get_sort_fields(sort)

        cursor_payload: dict = await SECURITY.decode_cursor(cursor, order)

        if not cursor_payload:
            """get records from the first record in db"""

            if order.lower() == "desc":
                filter_order = desc(*sort_fields)
            else:
                filter_order = asc(*sort_fields)

            stmt = (
                select(self.model)
                .where(*filter_conditions)
                .order_by(filter_order)
                .limit(limit + 1)
            )
        else:
            """continue with the last record viewed"""

            cursor_order: str = cursor_payload["order"]
            created_at: str = datetime.fromisoformat(cursor_payload["created_at"])

            if cursor_order == "desc":
                cursor_order = desc(*sort_fields)
                created_at_filter = self.model.created_at < created_at
            else:
                cursor_order = asc(*sort_fields)
                created_at_filter = self.model.created_at > created_at

            stmt = (
                select(self.model)
                .where(*filter_conditions, created_at_filter)
                .order_by(cursor_order)
                .limit(limit + 1)
            )

        res = await self._async_session.execute(stmt)
        records = res.scalars().all()

        has_more: bool = len(records) > limit

        payload: dict = {
            "created_at": records[:limit][-1].created_at.isoformat(),
            "order": cursor_payload["order"] if cursor_payload else order,
        }
        next_cursor: str = await SECURITY.encode_cursor(payload)

        return {"data": records[:limit], "cursor": next_cursor if has_more else None}

    async def get_record(self, **filters) -> SqlalchemyModel | None:
        filter_conditions: list[Any] = self._get_filters(**filters)

        res = await self._async_session.execute(
            select(self.model).where(*filter_conditions)
        )
        return res.scalar()

    async def update_records(self, fields_to_update: dict[str, Any], **filters):
        filter_conditions: list[Any] = self._get_filters(**filters)
        await self._async_session.execute(
            update(self.model).where(*filter_conditions).values(fields_to_update)
        )

    @abstractmethod
    def _entity_to_model(self, entity: Entity) -> SqlalchemyModel:
        raise NotImplementedError("Subclasses must implement _entity_to_model method")

    @abstractmethod
    def _get_filters(self, **filters) -> list[Any]:
        return []

    # sync db queries
    def get_sync_records(self, **filters) -> Sequence[SqlalchemyModel]:
        filter_conditions: list[Any] = self._get_filters(**filters)

        res = self._sync_session.execute(select(self.model).where(*filter_conditions))
        return res.scalars().all()

    def get_sync_record(self, **filters) -> SqlalchemyModel | None:
        filter_conditions: list[Any] = self._get_filters(**filters)

        res = self._sync_session.execute(select(self.model).where(*filter_conditions))
        return res.scalar()

    def sync_add(
        self, entity: Optional[Entity] = None, model: Optional[SqlalchemyModel] = None
    ):
        if not model:
            model: SqlalchemyModel = self._entity_to_model(entity)
        self._sync_session.add(model)

    def sync_flush(self):
        self._sync_session.flush()

    def sync_refresh(self, model: SqlalchemyModel):
        self._sync_session.refresh(model)

    def sync_commit(self):
        self._sync_session.commit()

    def sync_rollback(self):
        self._sync_session.rollback()

    def sync_delete(self, model: SqlalchemyModel):
        self._sync_session.delete(model)
        self._sync_session.flush()

    def close(self):
        self._sync_session.close()
