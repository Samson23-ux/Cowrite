import sentry_sdk
from uuid import UUID
from sentry_sdk import logger as sentry_logger


from app.util import get_user_email
from app.api.models.user import User
from app.api.models.document import Document
from app.api.repo.document import DocumentRepository
from app.core.exceptions import ServerError, DocumentNotFoundError
from app.api.schemas.document import DocumentCreate, DocumentInDb, DocumentResponse


class DocumentService:
    def __init__(self, doc_repo: DocumentRepository):
        self._doc_repo = doc_repo

    async def create_document(
        self, curr_user: User, document_payload: DocumentCreate
    ) -> DocumentResponse:
        user_email: str = get_user_email(curr_user)

        try:
            document: DocumentInDb = DocumentInDb(
                title=document_payload.title,
                content=document_payload.content,
                created_by=curr_user.id,
            )

            self._doc_repo.add(entity=document)
            await self._doc_repo.commit()

            document_db: Document = await self._get_document(document.id)

            sentry_logger.info("Document created!", extra={"email": user_email})
            return DocumentResponse.model_validate(document_db)
        except Exception as exc:
            self._doc_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating document", extra={"email": user_email}
            )
            raise ServerError() from exc

    async def _get_document(self, document_id: UUID) -> Document | None:
        return self._doc_repo.get_record(id=document_id)

    async def get_document(
        self, curr_user: User, document_id: UUID
    ) -> DocumentResponse:
        user_email: str = get_user_email(curr_user)

        try:
            document: Document | None = await self._get_document(document_id)

            if not document:
                sentry_logger.error(
                    "Document not found!",
                    extra={"id": document_id, "email": user_email},
                )
                raise DocumentNotFoundError(doc_id=document_id)

            sentry_logger.info(
                "Document retrieved!", extra={"id": document_id, "email": user_email}
            )
            return DocumentResponse.model_validate(document)
        except Exception as exc:
            if isinstance(exc, DocumentNotFoundError):
                raise DocumentNotFoundError(doc_id=document_id)

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating document", extra={"email": user_email}
            )
            raise ServerError() from exc
