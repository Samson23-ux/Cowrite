from uuid import UUID
from celery.exceptions import Reject


from app.worker import BaseTaskWithFailure
from app.worker import celery_app, event_bus
from app.api.schemas.event import TypingResponse


@celery_app.task(base=BaseTaskWithFailure, bind=True)
def check_expired_key(self):
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
