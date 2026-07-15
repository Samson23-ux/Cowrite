import json
from uuid import UUID
from celery.exceptions import Reject


from app.api.schemas.event import TypingResponse
from app.api.schemas.websocket import WebSocket as WebSocketSchema
from app.worker import (
    celery_app,
    event_bus,
    BaseTaskWithFailure,
    get_document_service,
    get_websocket_service,
)


@celery_app.task(base=BaseTaskWithFailure, bind=True)
def expired_typing_event(self):
    try:
        expire_channel: str = "__keyspace@0__:typing:"
        event: dict = event_bus.sync_get_message(expire_channel)

        if event:
            parsed_key: list[str] = event["channel"].split(":")
            doc_id: UUID = parsed_key[-2]
            user_id: UUID = parsed_key[-1]

            typing_response: dict = TypingResponse(
                doc_id=doc_id, user_id=user_id, mode="stopped"
            ).model_dump()
            event_bus.sync_publish(f"room:{doc_id}", typing_response)
    except Exception as exc:
        raise Reject(exc, requeue=False)


@celery_app.task(base=BaseTaskWithFailure, bind=True)
def expired_presence_event(self):
    try:
        document_service = get_document_service()
        websocket_service = get_websocket_service()

        expire_channel: str = "__keyspace@0__:presence:"
        event: dict = event_bus.sync_get_message(expire_channel)

        if event:
            parsed_key: list[str] = event["channel"].split(":")
            doc_id: UUID = parsed_key[-2]
            schema_json: dict = json.loads(parsed_key[-1])

            websocket_schema: WebSocketSchema = WebSocketSchema.model_validate(schema_json)
            websocket_service.sync_cleanup_connection(
                doc_id, event_bus, websocket_schema, document_service
            )
    except Exception as exc:
        raise Reject(exc, requeue=False)
