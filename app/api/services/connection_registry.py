import sentry_sdk
from sentry_sdk import logger as sentry_logger
from fastapi import WebSocket, WebSocketDisconnect


from app.api.services.event import EventBus
from app.api.repo.redis import RedisRepository
from app.api.schemas.websocket import WebSocket as WebSocketSchema


class ConnectionRegistry:
    """
    Contains mapping of documents and a list of connection,
    connection/disconnection from a room and lifecycle management
    """

    def __init__(self, redis_repo: RedisRepository):
        self._redis_repo = redis_repo
        self.active_connections: dict[str, list[WebSocketSchema]] = {}

    async def connect(
        self,
        doc_id: str,
        websocket_schema: WebSocketSchema,
        event_bus: EventBus,
        channel: str,
    ):
        user_id: str = websocket_schema.user_id
        if doc_id not in self.active_connections:
            self.active_connections[doc_id] = []

        if await self._redis_repo.get_set(f"user:{user_id}:{doc_id}"):
            await event_bus.subscribe(
                channel
            )  # subscribe on first connection to doc room

        if websocket_schema not in self.active_connections[doc_id]:
            self.active_connections[doc_id].append(websocket_schema)

        sentry_logger.info(
            "Document room joined!",
            extra={"doc_id": doc_id, "user_id": user_id},
        )

    async def disconnect(
        self,
        doc_id: str,
        websocket_schema: WebSocketSchema,
        event_bus: EventBus,
        channel: str,
    ):
        user_id: str = websocket_schema.user_id
        if doc_id in self.active_connections:
            try:
                self.active_connections[doc_id].remove(websocket_schema)

                sentry_logger.info(
                    "Connection removed from room!",
                    extra={"doc_id": doc_id, "user_id": websocket_schema.user_id},
                )

                if not self.active_connections[doc_id]:
                    del self.active_connections[doc_id]

                if not await self._redis_repo.get_set(f"user:{user_id}:{doc_id}"):
                    await event_bus.subscribe(
                        channel
                    )   # unsubscribe when doc room becomes empty

                    sentry_logger.info(
                        "Document room closed!", extra={"doc_id": doc_id}
                    )
            except ValueError:
                sentry_logger.error(
                    "Connection not present in room",
                    extra={"doc_id": doc_id, "user_id": user_id},
                )

    def get_connections(self, doc_id: str) -> list[WebSocketSchema]:
        if doc_id in self.active_connections:
            return self.active_connections[doc_id]
        return []

    def get_room_connections(self, doc_id: str) -> int:
        if doc_id in self.active_connections:
            return len(self.active_connections[doc_id])
        return 0

    def check_connectivity(
        self, doc_id: str, websocket_schema: WebSocketSchema
    ) -> bool:
        try:
            return websocket_schema in self.active_connections[doc_id]
        except KeyError:
            return False

    async def broadcast(
        self,
        data: dict,
        doc_id: str,
        websocket_schema: WebSocketSchema,
    ):
        """Send events to the connected client"""
        if doc_id in self.active_connections:
            if websocket_schema not in self.active_connections[doc_id]:
                return

            websocket: WebSocket = websocket_schema.websocket
            try:
                await websocket.send_json(data)
            except WebSocketDisconnect as exc:
                raise WebSocketDisconnect(code=exc.code, reason=exc.reason)
