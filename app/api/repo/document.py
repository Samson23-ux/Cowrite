from app.api.repo.base import BaseRepository
from app.api.models.document import Document
from app.api.schemas.document import DocumentBase


class DocumentRepository(BaseRepository[DocumentBase, Document]):
    model = Document

    def _entity_to_model(self, entity):
        return Document(**entity.model_dump())

    def _get_filters(self, **filters):
        filter_conditions = []

        if "id" in filters:
            filter_conditions.append(self.model.id == filters["id"])
        if "created_by" in filters:
            filter_conditions.append(self.model.created_by == filters["created_by"])

        return filter_conditions
