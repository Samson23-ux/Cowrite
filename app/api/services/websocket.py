import json
import asyncio
import sentry_sdk
from uuid import UUID
from sqlalchemy import Sequence
from pydantic import ValidationError
from sentry_sdk import logger as sentry_logger
from fastapi import WebSocket, WebSocketException


from app.api.services.event import EventBus
from app.api.repo.redis import RedisRepository
from app.api.services.document import DocumentService
from app.api.services.transformation import Transformation
from app.api.models.document import Document, DocumentMember
from app.api.schemas.websocket import WebSocket as WebSocketSchema
from app.api.services.connection_registry import ConnectionRegistry
from app.api.schemas.document import DocumentMember as DocumentMemberSchema
from app.api.schemas.event import (
    JoinEvent,
    JoinedResponse,
    UserJoinedResponse,
    LeaveEvent,
    LeftResponse,
    CursorEvent,
    CursorResponse,
    Operation,
    OperationEvent,
    OperationResponse,
    AckResponse,
    PresenceResponse,
    PingEvent,
    PongResponse,
    TypingEvent,
    TypingResponse,
)


class WebSocketService:
    def __init__(self, registry: ConnectionRegistry, redis: RedisRepository):
        self._redis = redis
        self._registry = registry

    async def cleanup_connection(
        self,
        doc_id: UUID,
        user_id: UUID,
        event_bus: EventBus,
        websocket_schema: WebSocketSchema,
        document_service: DocumentService,
    ):
        try:
            channel: str = f"room:{doc_id}"
            await self._registry.disconnect(
                doc_id, websocket_schema, event_bus, channel
            )

            member: Document | None = await document_service._get_document_member(
                document_id=doc_id, user_id=user_id
            )

            if member:
                await document_service._delete_document_member(member, user_id, doc_id)

            await self._redis.delete_key(f"presence:{doc_id}:{user_id}")
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while cleaning connection",
                extra={"doc_id": doc_id, "user_id": user_id},
            )
            raise WebSocketException(code=1011, reason="Internal Server Error")

    async def receive_json(self, websocket: WebSocket, timeout: int = 30):
        try:
            message = asyncio.wait_for(websocket.receive_json(), timeout=timeout)
            return message
        except asyncio.TimeoutError, asyncio.CancelledError:
            return

    async def receive_client_message(
        self,
        event_bus: EventBus,
        websocket: WebSocket,
        trans: Transformation,
        doc_id: UUID,
        user_id: UUID,
        user_email: str,
        display_name: str,
        user_docs: list[UUID],
        message: dict,
        document_service: DocumentService,
    ):
        if "type" not in message:
            raise WebSocketException(code=1003, reason="Missing event type")

        channel: str = f"room:{doc_id}"
        type: str = message.get("type").lower()

        if type == "join":
            await self.process_join_event(
                event_bus,
                websocket,
                doc_id,
                channel,
                user_id,
                user_email,
                display_name,
                user_docs,
                message,
                document_service,
            )
        elif type == "leave":
            await self.process_join_event(
                event_bus,
                websocket,
                doc_id,
                channel,
                user_id,
                user_email,
                user_docs,
                message,
                document_service,
            )
        elif type == "operation":
            await self.process_operation_event(
                doc_id,
                channel,
                user_id,
                message,
                user_email,
                event_bus,
                websocket,
                trans,
                document_service,
            )
        elif type == "cursor":
            await self.process_cursor_event(
                doc_id, channel, user_id, message, event_bus
            )
        elif type == "typing":
            await self.process_typing_event(
                doc_id, channel, user_id, message, event_bus
            )
        elif type == "ping":
            await self.process_ping_event(
                doc_id, user_id, user_email, message, websocket
            )

    async def receive_room_message(
        self,
        websocket: WebSocket,
        doc_id: UUID,
        user_id: UUID,
        user_email: str,
        message: dict,
    ):
        try:
            websocket_schema: WebSocketSchema = WebSocketSchema(
                websocket=websocket, user_id=user_id, user_email=user_email
            )
            await self._registry.broadcast(doc_id, websocket_schema, message)
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while broadcasting message",
                extra={"doc_id": doc_id, "user_id": user_id},
            )
            raise WebSocketException(code=1011, reason="Internal Server Error")

    async def process_join_event(
        self,
        event_bus: EventBus,
        websocket: WebSocket,
        doc_id: UUID,
        channel: str,
        user_id: UUID,
        user_email: str,
        display_name: str,
        user_docs: list[UUID],
        message: dict,
        document_service: DocumentService,
    ):
        try:
            _ = JoinEvent.model_validate(message)

            websocket_schema: WebSocketSchema = WebSocketSchema(
                websocket=websocket, user_id=user_id, user_email=user_email
            )
            self._registry.connect(doc_id, websocket_schema, event_bus, channel)

            document: Document | None = await document_service._get_document(doc_id)
            if not document:
                sentry_logger.error(
                    "Document not found!", extra={"doc_id": doc_id, "user_id": user_id}
                )
                raise WebSocketException(code=1008, reason="Document not found")

            document_member: DocumentMemberSchema = DocumentMemberSchema(
                user_id=user_id, doc_id=doc_id, role="viewer"
            )
            await document_service._create_document_member(document_member)

            presence_key: str = f"presence:{doc_id}:{user_id}"
            await self._redis.set_key(presence_key, display_name, 30)

            user_joined_response: dict = UserJoinedResponse(
                doc_id=doc_id, user_id=user_id, display_name=display_name
            ).model_dump()
            await event_bus.publish(channel, user_joined_response)

            document_members: Sequence[UUID] = (
                await document_service._get_document_members(document_id=doc_id)
            )
            presence: dict = PresenceResponse(
                doc_id=doc_id, users=document_members
            ).model_dump()
            await event_bus.publish(channel, presence)

            joined_response: dict = JoinedResponse(
                doc_id=doc_id,
                content=document.content,
                seq=document.sequence,
                presence=document_members,
            ).model_dump()
            await self._registry.broadcast(doc_id, websocket_schema, joined_response)

            user_docs.append(doc_id)
        except ValidationError:
            sentry_logger.error(
                "Invalid payload received for join event",
                extra={"doc_id": doc_id, "user_id": user_id},
            )
            raise WebSocketException(code=1003, reason="Invalid payload!")

    async def process_leave_event(
        self,
        event_bus: EventBus,
        websocket: WebSocket,
        doc_id: UUID,
        channel: str,
        user_id: UUID,
        user_email: str,
        user_docs: list[UUID],
        message: dict,
        document_service: DocumentService,
    ):
        try:
            _ = LeaveEvent.model_validate(message)

            websocket_schema: WebSocketSchema = WebSocketSchema(
                websocket=websocket, user_id=user_id, user_email=user_email
            )
            self._registry.disconnect(doc_id, websocket_schema, event_bus, channel)

            document_member: DocumentMember | None = (
                await document_service._get_document_member(
                    document_id=doc_id, user_id=user_id
                )
            )

            if not document_member:
                sentry_logger.error(
                    "Document member not found!",
                    extra={"doc_id": doc_id, "user_id": user_id},
                )
                raise WebSocketException(
                    code=1008, reason="Client not a member of the document"
                )

            await document_service._delete_document_member(
                document_member, user_id, doc_id
            )

            left_response: dict = LeftResponse(
                doc_id=doc_id, user_id=user_id
            ).model_dump()
            await event_bus.publish(channel, left_response)

            document_members: Sequence[UUID] = (
                await document_service._get_document_members(document_id=doc_id)
            )
            presence: dict = PresenceResponse(
                doc_id=doc_id, users=document_members
            ).model_dump()
            await event_bus.publish(channel, presence)

            user_docs.remove(doc_id)
        except ValidationError:
            sentry_logger.error(
                "Invalid payload received for leave event",
                extra={"doc_id": doc_id, "user_id": user_id},
            )
        except ValueError:
            sentry_logger.error(
                "Document member not found!",
                extra={"doc_id": doc_id, "user_id": user_id},
            )
            raise WebSocketException(code=1003, reason="Invalid payload!")

    async def process_operation_event(
        self,
        doc_id: UUID,
        channel: str,
        user_id: UUID,
        message: dict,
        user_email: str,
        event_bus: EventBus,
        websocket: WebSocket,
        trans: Transformation,
        document_service: DocumentService,
    ):
        try:
            op2: Operation = Operation(
                kind=message.get("kind"),
                pos=message.get("pos"),
                text=message.get("text"),
            )
            op_event: OperationEvent = OperationEvent(
                doc_id=doc_id, op=op2, base_seq=message.get("base_seq")
            )

            document: Document | None = await document_service._get_document(doc_id)
            if not document:
                sentry_logger.error(
                    "Document not found!", extra={"doc_id": doc_id, "user_id": user_id}
                )
                raise WebSocketException(code=1008, reason="Document not found")

            seq_key: str = f"doc:{doc_id}:seq"
            curr_seq: int = int(await self._redis.get_key(seq_key))

            base_seq: int = op_event.base_seq

            if base_seq < curr_seq:
                # transform operations since base_seq
                key: str = f"doc{doc_id}:ops"
                logs: list[str] = await self._redis.get_sorted_set(
                    key, base_seq + 1, curr_seq
                )

                temp_pos = None
                op_log: list[dict] = [json.loads(l) for l in logs]

                for log in op_log:
                    op1: Operation = Operation.model_validate(log)
                    temp_pos: int = await trans.transform(op1, op2)

                op2.pos = temp_pos
                doc_content = list(document.content)
                updated_doc = await trans.apply_operation(doc_content, op2)
            elif base_seq == curr_seq:
                # apply change to doc
                doc_content = list(document.content)
                updated_doc = await trans.apply_operation(doc_content, op2)
            else:
                sentry_logger.error(
                    "Invalid sequence number receieved from client!",
                    extra={
                        "doc_id": doc_id,
                        "user_id": user_id,
                        "base_seq": base_seq,
                        "seq": curr_seq,
                    },
                )
                raise WebSocketException(code=1003, reason="Invalid seq receieved")

            new_seq: int = await self._redis.increment_counter(
                seq_key
            )  # redis incr for atomicity and concurrent requests

            content: str = "".join(updated_doc)
            document.content = content
            document.sequence = new_seq

            await document_service._update_document(document, user_id, doc_id)

            op2_log = json.dumps(op2)
            await self._redis.create_sorted_set(key, op2_log)

            ack_resposne: AckResponse = AckResponse(
                doc_id=doc_id, seq=new_seq
            ).model_dump()
            websocket_schema: WebSocketSchema = WebSocketSchema(
                websocket=websocket, user_id=user_id, user_email=user_email
            )
            await self._registry.broadcast(doc_id, websocket_schema, ack_resposne)

            op_response: dict = OperationResponse(
                doc_id=doc_id, op=op2, seq=new_seq, user_id=user_id
            ).model_dump()
            await event_bus.publish(channel, op_response)
        except ValidationError:
            sentry_logger.error(
                "Invalid payload received for operation event",
                extra={"doc_id": doc_id, "user_id": user_id},
            )

    async def process_cursor_event(
        self,
        doc_id: UUID,
        channel: str,
        user_id: UUID,
        message: dict,
        event_bus: EventBus,
    ):
        try:
            cursor_event = CursorEvent.model_validate(message)
            cursor_response: dict = CursorResponse(
                doc_id=doc_id, user_id=user_id, pos=cursor_event.pos
            ).model_dump()
            await event_bus.publish(channel, cursor_response)
        except ValidationError:
            sentry_logger.error(
                "Invalid payload received for cursor event",
                extra={"doc_id": doc_id, "user_id": user_id},
            )
            raise WebSocketException(code=1003, reason="Invalid payload!")

    async def process_ping_event(
        self,
        doc_id: UUID,
        user_id: UUID,
        user_email: str,
        message: dict,
        websocket: WebSocket,
    ):
        try:
            _ = PingEvent.model_validate(message)

            key: str = f"presence:{doc_id}:{user_id}"
            await self._redis.reset_key_ttl(key, 30)

            websocket_schema: WebSocketSchema = WebSocketSchema(
                websocket=websocket, user_id=user_id, user_email=user_email
            )
            await self._registry.broadcast(
                doc_id, websocket_schema, PongResponse().model_dump()
            )
        except ValidationError:
            sentry_logger.error(
                "Invalid payload received for ping event",
                extra={"doc_id": doc_id, "user_id": user_id},
            )
            raise WebSocketException(code=1003, reason="Invalid payload!")

    async def process_typing_event(
        self,
        doc_id: UUID,
        channel: str,
        user_id: UUID,
        message: dict,
        event_bus: EventBus,
    ):
        try:
            _ = TypingEvent.model_validate(message)

            key: str = f"typing:{doc_id}:{user_id}"
            await self._redis.set_key(key, "1", 3)

            typing_response: dict = TypingResponse(
                doc_id=doc_id, user_id=user_id, mode="started"
            ).model_dump()
            await event_bus.publish(channel, typing_response)
        except ValidationError:
            sentry_logger.error(
                "Invalid payload received for typing event",
                extra={"doc_id": doc_id, "user_id": user_id},
            )
            raise WebSocketException(code=1003, reason="Invalid payload!")
