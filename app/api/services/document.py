import sentry_sdk
from uuid import UUID
from sqlalchemy import Sequence
from fastapi import WebSocketException
from sentry_sdk import logger as sentry_logger


from app.util import get_user_email
from app.api.models.user import User
from app.api.repo.redis import RedisRepository
from app.api.repo.document import DocumentRepository
from app.api.models.document import Document, DocumentMember
from app.api.repo.document_member import DocumentMemberRepository
from app.core.exceptions import ServerError, DocumentNotFoundError
from app.api.schemas.document import (
    DocumentCreate,
    DocumentInDb,
    DocumentResponse,
    DocumentMember as DocumentMemberSchema,
)


class DocumentService:
    def __init__(
        self,
        redis_repo: RedisRepository,
        doc_repo: DocumentRepository,
        member_repo: DocumentMemberRepository,
    ):
        self._doc_repo = doc_repo
        self._redis_repo = redis_repo
        self._member_repo = member_repo

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

            document_db: Document = await self._get_document(id=document.id)

            seq_key: str = f"doc:{document_db.id}:seq"
            await self._redis_repo.increment_counter(seq_key)

            extra: dict = {"email": user_email}
            sentry_logger.info("Document created!", extra=extra)
            return DocumentResponse.model_validate(document_db)
        except Exception as exc:
            self._doc_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error("Error occurred while creating document", extra=extra)
            raise ServerError() from exc

    async def _create_document_member(self, document_member: DocumentMemberSchema):
        try:
            self._member_repo.add(entity=document_member)
            await self._member_repo.commit()

            extra: dict = {
                "doc_id": document_member.doc_id,
                "user_id": document_member.user_id,
            }
            sentry_logger.info(
                "Document member created!",
                extra=extra,
            )
        except Exception as exc:
            await self._member_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while creating document member",
                extra=extra,
            )
            raise WebSocketException(code=1011, reason="Internal Server Error")

    async def _get_document(self, **filters) -> Document | None:
        return await self._doc_repo.get_record(**filters)

    async def _get_document_members(self, **filters) -> Sequence[UUID]:
        return await self._member_repo.get_document_members(**filters)

    async def _get_document_member(self, **filters) -> DocumentMember | None:
        return await self._member_repo.get_record(**filters)

    async def get_document(
        self, curr_user: User, document_id: UUID
    ) -> DocumentResponse:
        user_email: str = get_user_email(curr_user)

        try:
            document: Document | None = await self._get_document(id=document_id)

            extra: dict = {"id": document_id, "email": user_email}
            if not document:
                sentry_logger.error(
                    "Document not found!",
                    extra=extra,
                )
                raise DocumentNotFoundError(doc_id=document_id)

            sentry_logger.info("Document retrieved!", extra=extra)
            return DocumentResponse.model_validate(document)
        except Exception as exc:
            if isinstance(exc, DocumentNotFoundError):
                raise DocumentNotFoundError(doc_id=document_id)

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occurred while creating document", extra={"email": user_email}
            )
            raise ServerError() from exc

    async def _update_document(self, document: Document, user_id: UUID, doc_id: UUID):
        try:
            self._doc_repo.add(model=document)
            await self._doc_repo.commit()

            extra: dict = {"doc_id": doc_id, "user_id": user_id}
            sentry_logger.info("Document updated!", extra=extra)
        except Exception as exc:
            await self._doc_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while updating document",
                extra=extra,
            )
            raise WebSocketException(code=1011, reason="Internal Server Error")

    async def _update_document_member(
        self, document: DocumentMember, user_id: UUID, doc_id: UUID
    ):
        try:
            self._member_repo.add(model=document)
            await self._member_repo.commit()

            extra: dict = {"doc_id": doc_id, "user_id": user_id}
            sentry_logger.info("Document member updated!", extra=extra)
        except Exception as exc:
            await self._member_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while updating document memeber",
                extra=extra,
            )
            raise WebSocketException(code=1011, reason="Internal Server Error")

    async def _update_member_role(self, role: str, **filters):
        try:
            await self._member_repo.update_role(role, **filters)
            await self._member_repo.commit()

            extra: dict = {"doc_id": filters["doc_id"], "user_id": filters["user_id"]}
            sentry_logger.info("Document member role updated!", extra=extra)
        except Exception as exc:
            await self._member_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while updating document memeber role",
                extra=extra,
            )
            raise WebSocketException(code=1011, reason="Internal Server Error")

    async def _delete_document_member(
        self, member: DocumentMember, user_id: UUID, doc_id: UUID
    ):
        try:
            await self._member_repo.delete(member)
            await self._member_repo.commit()

            extra: dict = {"doc_id": doc_id, "user_id": user_id}
            sentry_logger.info("Document member deleted!", extra=extra)
        except Exception as exc:
            await self._member_repo.rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while deleting document member",
                extra=extra,
            )
            raise WebSocketException(code=1011, reason="Internal Server Error")

    # sync

    def _sync_get_document_member(self, **filters) -> DocumentMember | None:
        return self._member_repo.get_sync_record(**filters)

    def _sync_delete_document_member(
        self, member: DocumentMember, user_id: UUID, doc_id: UUID
    ):
        try:
            self._member_repo.sync_delete(member)
            self._member_repo.sync_commit()

            extra: dict = {"doc_id": doc_id, "user_id": user_id}
            sentry_logger.info("Document member deleted!", extra=extra)
        except Exception as exc:
            self._member_repo.sync_rollback()

            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while deleting document member",
                extra=extra,
            )
            raise WebSocketException(code=1011, reason="Internal Server Error")
