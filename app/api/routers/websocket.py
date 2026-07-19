from uuid import uuid4
from datetime import datetime, timezone
import sentry_sdk.logger as sentry_logger
from fastapi import APIRouter, WebSocket, WebSocketDisconnect


from app.api.schemas.websocket import WebSocket as WebsocketSchema
from app.deps import (
    WebSocketAuth,
    EventBusDep,
    WebSocketServiceDep,
    DocumentServiceDep,
    TransformationDep,
)

router = APIRouter()


@router.websocket("/ws")
async def connect(
    websocket: WebSocket,
    token: WebSocketAuth,
    event_bus: EventBusDep,
    trans: TransformationDep,
    document_service: DocumentServiceDep,
    websocket_service: WebSocketServiceDep,
):
    doc_id = None

    curr_user, user_email = token
    user_id = str(curr_user.id)

    await websocket.accept()
    websocket_schema: WebsocketSchema = WebsocketSchema(
        connection_id=str(uuid4()),
        websocket=websocket,
        user_id=user_id,
        user_email=user_email,
        joined_at=datetime.now(timezone.utc).isoformat(),
    )

    try:
        while True:
            client_message = await websocket_service.receive_json(websocket)

            if client_message:
                doc_id = client_message.get("doc_id", "")
                await websocket_service.receive_client_message(
                    doc_id,
                    client_message,
                    curr_user.display_name,
                    event_bus,
                    trans,
                    websocket_schema,
                    document_service,
                )

            await websocket_service.receive_room_message(doc_id, event_bus, websocket_schema)
    except WebSocketDisconnect:
        if doc_id:
            await websocket_service.cleanup_connection(
                doc_id,
                event_bus,
                websocket_schema,
                document_service,
                disconnect=True,
            )
        sentry_logger.error("Websocket disconnected!", extra={"id": user_id})
