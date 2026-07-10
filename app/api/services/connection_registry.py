import sentry_sdk
from uuid import UUID
from fastapi import WebSocket, WebSocketDisconnect
from sentry_sdk import logger as sentry_logger


from app.api.schemas.websocket import WebSocket as WebSocketSchema


class ConnectionRegistry:
    def __init__(self):
        self.active_connections: dict[UUID, list[WebSocketSchema]] = {}

    async def connect(self, doc_id: UUID, websocket_schema: WebSocketSchema):
        if doc_id not in self.active_connections:
            self.active_connections[doc_id] = []
        self.active_connections[doc_id].append(websocket_schema)

        sentry_logger.info(
            "Document room joined!",
            extra={"doc_id": doc_id, "user_id": websocket_schema.user_id},
        )

    async def disconnect(self, doc_id: UUID, websocket_schema: WebSocketSchema):
        if doc_id in self.active_connections:
            try:
                self.active_connections[doc_id].remove(websocket_schema)

                sentry_logger.info(
                    "Connection removed from room!",
                    extra={"doc_id": doc_id, "user_id": websocket_schema.user_id},
                )

                if not self.active_connections[doc_id]:
                    del self.active_connections[doc_id]

                    sentry_logger.info(
                        "Document room closed!", extra={"doc_id": doc_id}
                    )
            except ValueError:
                sentry_logger.error(
                    "Connection not present in room",
                    extra={"doc_id": doc_id, "user_id": websocket_schema.user_id},
                )

    async def get_room_connections(self, doc_id: UUID) -> int:
        if doc_id in self.active_connections:
            return len(self.active_connections[doc_id])

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
