import sentry_sdk
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect
from sentry_sdk import logger as sentry_logger


from app.api.services.event import EventBus
from app.api.schemas.websocket import WebSocket as WebSocketSchema


class ConnectionRegistry:
    """
    Contains mapping of documents and a list of connection,
    connection/disconnection from a room and lifecycle management
    """

    def __init__(self):
        self.active_connections: dict[UUID, list[WebSocketSchema]] = {}

    async def connect(
        self,
        doc_id: UUID,
        websocket_schema: WebSocketSchema,
        event_bus: EventBus,
        channel: str,
    ):
        if doc_id not in self.active_connections:
            self.active_connections[doc_id] = []
            await event_bus.subscribe(
                channel
            )  # subscribe on first connection to doc room

        if websocket_schema not in self.active_connections[doc_id]:
            self.active_connections[doc_id].append(websocket_schema)

        sentry_logger.info(
            "Document room joined!",
            extra={"doc_id": doc_id, "user_id": websocket_schema.user_id},
        )

    async def disconnect(
        self,
        doc_id: UUID,
        websocket_schema: WebSocketSchema,
        event_bus: EventBus,
        channel: str,
    ):
        if doc_id in self.active_connections:
            try:
                self.active_connections[doc_id].remove(websocket_schema)

                sentry_logger.info(
                    "Connection removed from room!",
                    extra={"doc_id": doc_id, "user_id": websocket_schema.user_id},
                )

                if not self.active_connections[doc_id]:
                    del self.active_connections[doc_id]
                    await event_bus.unsubscribe(
                        channel
                    )  # unsubscribe when doc room becomes empty

                    sentry_logger.info(
                        "Document room closed!", extra={"doc_id": doc_id}
                    )
            except ValueError:
                sentry_logger.error(
                    "Connection not present in room",
                    extra={"doc_id": doc_id, "user_id": websocket_schema.user_id},
                )

    def get_connections(self, doc_id: UUID) -> list[WebSocketSchema]:
        if doc_id in self.active_connections:
            return self.active_connections[doc_id]
        return []

    def get_room_connections(self, doc_id: UUID) -> int:
        if doc_id in self.active_connections:
            return len(self.active_connections[doc_id])
        return 0

    def check_connectivity(
        self, doc_id: UUID, websocket_schema: WebSocketSchema
    ) -> bool:
        try:
            return websocket_schema in self.active_connections[doc_id]
        except KeyError:
            return False

    async def broadcast(
        self, doc_id: UUID, websocket_schema: WebSocketSchema, data: dict
    ):
        """Send events to the connected client"""
        if doc_id in self.active_connections:
            if websocket_schema not in self.active_connections[doc_id]:
                return

            websocket: WebSocket = websocket_schema.websocket
            try:
                await websocket.send_json(data)
            except WebSocketDisconnect as exc:
                sentry_sdk.capture_exception(exc)
                sentry_logger.error(
                    "Websocket disconnected",
                    extra={"doc_id": doc_id, "user_id": websocket_schema.user_id},
                )

                await self.disconnect(doc_id, websocket_schema)

    # sync

    def sync_disconnect(
        self,
        doc_id: UUID,
        websocket_schema: WebSocketSchema,
        event_bus: EventBus,
        channel: str,
    ):
        if doc_id in self.active_connections:
            try:
                self.active_connections[doc_id].remove(websocket_schema)

                sentry_logger.info(
                    "Connection removed from room!",
                    extra={"doc_id": doc_id, "user_id": websocket_schema.user_id},
                )

                if not self.active_connections[doc_id]:
                    del self.active_connections[doc_id]
                    event_bus.sync_unsubscribe(
                        channel
                    )  # unsubscribe when doc room becomes empty

                    sentry_logger.info(
                        "Document room closed!", extra={"doc_id": doc_id}
                    )
            except ValueError:
                sentry_logger.error(
                    "Connection not present in room",
                    extra={"doc_id": doc_id, "user_id": websocket_schema.user_id},
                )
