from uuid import UUID
from typing import Any
from sqlalchemy import select, Sequence


from app.api.repo.base import BaseRepository
from app.api.models.document import DocumentMember
from app.api.schemas.document import DocumentMember as DocumentMemberSchema


class DocumentMemberRepository(BaseRepository[DocumentMember, DocumentMember]):
    model = DocumentMember

    def _entity_to_model(self, entity):
        return DocumentMemberSchema(**entity.model_dump())

    def _get_filters(self, **filters):
        filter_conditions = []

        if "document_id" in filters:
            filter_conditions.append(self.model.document_id == filters["document_id"])
        if "user_id" in filters:
            filter_conditions.append(self.model.user_id == filters["user_id"])

        return filter_conditions

    async def get_document_members(self, **filters) -> Sequence[UUID]:
        filter_conditions: list[Any] = self._get_filters(**filters)

        res = await self._async_session.execute(
            select(self.model.document_id).where(*filter_conditions)
        )
        return res.scalars().all()
