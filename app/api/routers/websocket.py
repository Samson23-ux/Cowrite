from typing import Optional
import sentry_sdk.logger as sentry_logger
from fastapi import APIRouter, WebSocket, Request, WebSocketDisconnect


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
    request: Request,
    websocket: WebSocket,
    token: WebSocketAuth,
    event_bus: EventBusDep,
    trans: TransformationDep,
    document_service: DocumentServiceDep,
    websocket_service: WebSocketServiceDep,
    seq: Optional[int] = None,
):
    # replay if seq is received
    doc_id = None

    curr_user, user_email = token
    user_id = curr_user.id

    await websocket.accept()
    websocket_schema: WebsocketSchema = WebsocketSchema(
        websocket=websocket, user_id=user_id, user_email=user_email
    )

    user_docs = []

    while True:
        try:
            client_message = await websocket_service.receive_json(websocket)
            if client_message:
                doc_id = client_message.get("doc_id", "")
                await websocket_service.receive_client_message(
                    event_bus,
                    websocket,
                    trans,
                    doc_id,
                    user_id,
                    user_email,
                    curr_user.display_name,
                    user_docs,
                    client_message,
                    document_service,
                )

            for id in user_docs:
                # get message from subscribed channels
                room_message = await event_bus.get_message(f"room:{id}")
                if room_message:
                    # only process other clients message from redis subpub
                    if room_message["user_id"] != str(user_id):
                        await websocket_service.receive_room_message(
                            websocket, id, user_id, user_email, room_message
                        )
        except WebSocketDisconnect:
            if doc_id:
                await websocket_service.cleanup_connection(
                    doc_id,
                    user_id,
                    event_bus,
                    websocket_schema,
                    document_service,
                )

                try:
                    user_docs.remove(doc_id)
                except ValueError:
                    sentry_logger.error(
                        "Document id not found in user_docs",
                        extra={"user_id": user_id, "doc_id": doc_id},
                    )
            sentry_logger.error("Websocket disconnected!", extra={"id": user_id})
