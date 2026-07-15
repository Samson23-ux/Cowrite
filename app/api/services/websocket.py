import json
import asyncio
import sentry_sdk
from uuid import UUID
from sqlalchemy import Sequence
from pydantic import ValidationError
from datetime import datetime, timezone
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
    ReplayEvent,
)


class WebSocketService:
    def __init__(self, registry: ConnectionRegistry, redis: RedisRepository):
        self._redis = redis
        self._registry = registry

    async def cleanup_connection(
        self,
        doc_id: UUID,
        event_bus: EventBus,
        websocket_schema: WebSocketSchema,
        document_service: DocumentService,
    ):
        try:
            user_id: UUID = websocket_schema.user_id

            channel: str = f"room:{doc_id}"
            await self._registry.disconnect(
                doc_id, websocket_schema, event_bus, channel
            )

            member: Document | None = await document_service._get_document_member(
                document_id=doc_id, user_id=user_id
            )

            if member:
                await document_service._delete_document_member(member, user_id, doc_id)

            schema_json: str = json.dumps(websocket_schema.model_dump())
            await self._redis.delete_key(f"presence:{doc_id}:{schema_json}")

            connections: list[WebSocketSchema] = self._registry.get_connections(
                doc_id
            )
            document_members: list[UUID] = [c.user_id for c in connections]

            presence: dict = PresenceResponse(
                doc_id=doc_id, users=document_members
            ).model_dump()
            await event_bus.publish(channel, presence)
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
        doc_id: str,
        message: dict,
        display_name: str,
        event_bus: EventBus,
        user_docs: list[UUID],
        trans: Transformation,
        websocket_schema: WebSocketSchema,
        document_service: DocumentService,
    ):
        if "type" not in message:
            raise WebSocketException(code=1003, reason="Missing event type")

        channel: str = f"room:{doc_id}"
        type: str = message.get("type").lower()

        if type == "join":
            await self.process_join_event(
                doc_id,
                channel,
                message,
                display_name,
                event_bus,
                user_docs,
                document_service,
                websocket_schema,
            )
        elif type == "leave":
            await self.process_leave_event(
                doc_id,
                channel,
                message,
                event_bus,
                user_docs,
                websocket_schema,
                document_service,
            )
        elif type == "operation":
            await self.process_operation_event(
                doc_id,
                channel,
                message,
                event_bus,
                trans,
                websocket_schema,
                document_service,
            )
        elif type == "cursor":
            await self.process_cursor_event(
                doc_id, channel, message, event_bus, websocket_schema
            )
        elif type == "typing":
            await self.process_typing_event(
                doc_id, channel, message, event_bus, websocket_schema
            )
        elif type == "replay":
            await self.process_replay_event(doc_id, message, websocket_schema)
        elif type == "ping":
            await self.process_ping_event(doc_id, message, websocket_schema)

    async def receive_room_message(
        self,
        websocket: WebSocket,
        doc_id: str,
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
        doc_id: str,
        channel: str,
        message: dict,
        display_name: str,
        event_bus: EventBus,
        user_docs: list[UUID],
        document_service: DocumentService,
        websocket_schema: WebSocketSchema,
    ):
        """
        Connect event to an existing document room.
        In the case of server failures or crash, a join
        event is sent to reconnect to room
        """
        user_id: UUID = websocket_schema.user_id
        extra: dict = {"doc_id": doc_id, "user_id": user_id}

        try:
            _ = JoinEvent.model_validate(message)
            self._registry.connect(doc_id, websocket_schema, event_bus, channel)

            document: Document | None = await document_service._get_document(doc_id)
            if not document:
                sentry_logger.error("Document not found!", extra=extra)
                raise WebSocketException(code=1008, reason="Document not found")

            document_member_db: DocumentMember | None = (
                await document_service._get_document_member(
                    document_id=doc_id, user_id=user_id
                )
            )

            if document_member_db:
                """catch duplicates when join events are sent after server failure"""
                document_member_db.joined_at = datetime.now(timezone.utc)
                await document_service._update_document_member(document_member_db)
            else:
                role: str = "author" if user_id == document.created_by else "viewer"
                document_member: DocumentMemberSchema = DocumentMemberSchema(
                    user_id=user_id, doc_id=doc_id, role=role
                )
                await document_service._create_document_member(document_member)

            schema_json: str = json.dumps(websocket_schema.model_dump())
            presence_key: str = f"presence:{doc_id}:{schema_json}"
            await self._redis.set_key(presence_key, display_name, 30)

            user_joined_response: dict = UserJoinedResponse(
                doc_id=doc_id, user_id=user_id, display_name=display_name
            ).model_dump()
            await event_bus.publish(channel, user_joined_response)

            connections: list[WebSocketSchema] = self._registry.get_connections(
                doc_id
            )
            document_members: list[UUID] = [c.user_id for c in connections]

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
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Invalid payload!")

    async def process_leave_event(
        self,
        doc_id: str,
        channel: str,
        message: dict,
        event_bus: EventBus,
        user_docs: list[UUID],
        websocket_schema: WebSocketSchema,
        document_service: DocumentService,
    ):
        user_id: UUID = websocket_schema.user_id
        extra: dict = {"doc_id": doc_id, "user_id": user_id}

        if not self._registry.check_connectivity(doc_id, websocket_schema):
            sentry_logger.error(
                "Client connection not found!",
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Client disconnected!")

        try:
            _ = LeaveEvent.model_validate(message)

            self._registry.disconnect(doc_id, websocket_schema, event_bus, channel)

            document_member: DocumentMember | None = (
                await document_service._get_document_member(
                    document_id=doc_id, user_id=user_id
                )
            )

            if not document_member:
                sentry_logger.error(
                    "Document member not found!",
                    extra=extra,
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

            connections: list[WebSocketSchema] = self._registry.get_connections(
                doc_id
            )
            document_members: list[UUID] = [c.user_id for c in connections]

            presence: dict = PresenceResponse(
                doc_id=doc_id, users=document_members
            ).model_dump()
            await event_bus.publish(channel, presence)

            user_docs.remove(doc_id)
        except ValidationError:
            sentry_logger.error(
                "Invalid payload received for leave event",
                extra=extra,
            )
        except ValueError:
            sentry_logger.error(
                "Document member not found!",
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Invalid payload!")

    async def process_operation_event(
        self,
        doc_id: str,
        channel: str,
        message: dict,
        event_bus: EventBus,
        trans: Transformation,
        websocket_schema: WebSocketSchema,
        document_service: DocumentService,
    ):
        user_id: UUID = websocket_schema.user_id
        extra: dict = {"doc_id": doc_id, "user_id": user_id}

        if not self._registry.check_connectivity(doc_id, websocket_schema):
            sentry_logger.error(
                "Client connection not found!",
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Client disconnected!")

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
                sentry_logger.error("Document not found!", extra=extra)
                raise WebSocketException(code=1008, reason="Document not found")

            seq_key: str = f"doc:{doc_id}:seq"
            curr_seq: int = int(await self._redis.get_key(seq_key))

            base_seq: int = op_event.base_seq

            if base_seq < curr_seq:
                # transform operations since base_seq
                key: str = f"doc{doc_id}:ops"
                logs: list[tuple] = await self._redis.get_sorted_set(
                    key, base_seq + 1, curr_seq
                )

                temp_pos = None
                op_log: list[dict] = [json.loads(l) for l, _ in logs]

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

            if user_id != document.created_by:
                await document_service._update_member_role(
                    "editor", doc_id=doc_id, user_id=user_id, role="viewer"
                )

            op2_log = json.dumps(op2)
            await self._redis.create_sorted_set(key, {op2_log: new_seq})

            ack_resposne: AckResponse = AckResponse(
                doc_id=doc_id, seq=new_seq
            ).model_dump()
            await self._registry.broadcast(doc_id, websocket_schema, ack_resposne)

            op_response: dict = OperationResponse(
                doc_id=doc_id, op=op2, seq=new_seq, user_id=user_id
            ).model_dump()
            await event_bus.publish(channel, op_response)
        except ValidationError:
            sentry_logger.error(
                "Invalid payload received for operation event",
                extra=extra,
            )

    async def process_cursor_event(
        self,
        doc_id: str,
        channel: str,
        message: dict,
        event_bus: EventBus,
        websocket_schema: WebSocketSchema,
    ):
        user_id: UUID = websocket_schema.user_id
        extra: dict = {"doc_id": doc_id, "user_id": user_id}

        if not self._registry.check_connectivity(doc_id, websocket_schema):
            sentry_logger.error(
                "Client connection not found!",
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Client disconnected!")

        try:
            cursor_event = CursorEvent.model_validate(message)
            cursor_response: dict = CursorResponse(
                doc_id=doc_id, user_id=user_id, pos=cursor_event.pos
            ).model_dump()
            await event_bus.publish(channel, cursor_response)
        except ValidationError:
            sentry_logger.error(
                "Invalid payload received for cursor event",
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Invalid payload!")

    async def process_ping_event(
        self,
        doc_id: str,
        message: dict,
        websocket_schema: WebSocketSchema,
    ):
        user_id: UUID = websocket_schema.user_id
        extra: dict = {"doc_id": doc_id, "user_id": user_id}

        if not self._registry.check_connectivity(doc_id, websocket_schema):
            sentry_logger.error(
                "Client connection not found!",
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Client disconnected!")

        try:
            _ = PingEvent.model_validate(message)

            schema_json: str = json.dumps(websocket_schema.model_dump())
            key: str = f"presence:{doc_id}:{schema_json}"
            await self._redis.reset_key_ttl(key, 30)

            await self._registry.broadcast(
                doc_id, websocket_schema, PongResponse().model_dump()
            )
        except ValidationError:
            sentry_logger.error(
                "Invalid payload received for ping event",
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Invalid payload!")

    async def process_typing_event(
        self,
        doc_id: str,
        channel: str,
        message: dict,
        event_bus: EventBus,
        websocket_schema: WebSocketSchema,
    ):
        user_id: UUID = websocket_schema.user_id
        extra: dict = {"doc_id": doc_id, "user_id": user_id}

        if not self._registry.check_connectivity(doc_id, websocket_schema):
            sentry_logger.error(
                "Client connection not found!",
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Client disconnected!")

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
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Invalid payload!")

    async def process_replay_event(
        self,
        doc_id: str,
        message: dict,
        websocket_schema: WebSocketSchema,
    ):
        user_id: UUID = websocket_schema.user_id
        extra: dict = {"doc_id": doc_id, "user_id": user_id}

        if not self._registry.check_connectivity(doc_id, websocket_schema):
            sentry_logger.error(
                "Client connection not found!",
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Client disconnected!")

        try:
            replay: ReplayEvent = ReplayEvent.model_validate(message)

            seq_key: str = f"doc:{doc_id}:seq"
            curr_seq: int = int(await self._redis.get_key(seq_key))

            key: str = f"doc{doc_id}:ops"
            logs: list[tuple] = await self._redis.get_sorted_set(
                key, replay.seq + 1, curr_seq, with_scores=True
            )

            op_log: list[tuple] = [(json.loads(l), seq) for l, seq in logs]

            for log, seq in op_log:
                operation: Operation = Operation.model_validate(log)
                op_response: dict = OperationResponse(
                    doc_id=doc_id, op=operation, seq=seq, user_id=user_id
                ).model_dump()
                await self._registry.broadcast(doc_id, websocket_schema, op_response)
        except ValidationError:
            sentry_logger.error(
                "Invalid payload received for replay event",
                extra=extra,
            )
            raise WebSocketException(code=1003, reason="Invalid payload!")
        
    # sync

    def sync_cleanup_connection(
        self,
        doc_id: str,
        event_bus: EventBus,
        websocket_schema: WebSocketSchema,
        document_service: DocumentService,
    ):
        try:
            user_id: UUID = websocket_schema.user_id

            channel: str = f"room:{doc_id}"
            self._registry.sync_disconnect(
                doc_id, websocket_schema, event_bus, channel
            )

            member: Document | None = document_service._sync_get_document_member(
                document_id=doc_id, user_id=user_id
            )

            if member:
                document_service._sync_delete_document_member(member, user_id, doc_id)

            connections: list[WebSocketSchema] = self._registry.get_connections(
                doc_id
            )
            document_members: list[UUID] = [c.user_id for c in connections]

            presence: dict = PresenceResponse(
                doc_id=doc_id, users=document_members
            ).model_dump()
            event_bus.sync_publish(channel, presence)
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while cleaning connection",
                extra={"doc_id": doc_id, "user_id": user_id},
            )
            raise WebSocketException(code=1011, reason="Internal Server Error")
