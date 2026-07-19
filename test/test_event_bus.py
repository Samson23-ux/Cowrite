import uuid
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


from app.api.services.event import EventBus


@pytest.fixture
def event_bus() -> EventBus:
    redis = AsyncMock()
    pubsub = AsyncMock()

    eb = EventBus(async_redis=redis)
    eb.TIMEOUT = 3
    eb.pubsub = pubsub

    return eb


class TestEventBus:
    CHANNEL = "test:channel"
    EVENT = {"data": "test"}
    SDK_PATH = "app.api.services.event.sentry_sdk"
    LOGGER_PATH = "app.api.services.event.sentry_logger"

    @pytest.mark.anyio
    async def test_subscribe(self, event_bus: EventBus):
        event_bus.pubsub.subscribe = AsyncMock(return_value=None)
        await event_bus.subscribe(self.CHANNEL)

        event_bus.pubsub.subscribe.assert_awaited_once_with(self.CHANNEL)

    @pytest.mark.anyio
    async def test_unsubscribe(self, event_bus: EventBus):
        await event_bus.subscribe(self.CHANNEL)

        event_bus.pubsub.unsubscribe = AsyncMock(return_value=None)
        await event_bus.unsubscribe(self.CHANNEL)

        event_bus.pubsub.unsubscribe.assert_awaited_once_with(self.CHANNEL)

    @pytest.mark.anyio
    async def test_publish_message(self, event_bus: EventBus):
        await event_bus.publish(self.CHANNEL, self.EVENT)
        event_bus._async_redis.publish.assert_awaited_once_with(
            self.CHANNEL, json.dumps(self.EVENT)
        )

    @pytest.mark.anyio
    async def test_publish_message_invalid_type(self, event_bus: EventBus):
        with patch(self.LOGGER_PATH) as logger:
            logger.error = MagicMock()

            await event_bus.publish(self.CHANNEL, {"id": uuid.uuid4()})
            logger.error.assert_called_once_with("Invalid payload received!")

    @pytest.mark.anyio
    async def test_publish_message_error(self, event_bus: EventBus):
        with patch(self.LOGGER_PATH) as logger, patch(self.SDK_PATH) as sdk:
            exc = Exception("Invalid type!")
            event_bus._async_redis.publish.side_effect = exc
            await event_bus.publish(self.CHANNEL, self.EVENT)

            logger.error.assert_called_once_with(
                "Error occured while publishing message to channel",
                extra={"channel": self.CHANNEL},
            )

            sdk.capture_exception.assert_called_once_with(exc)

    @pytest.mark.anyio
    async def test_get_message(self, event_bus: EventBus):
        event_bus.pubsub.get_message.return_value = {
            "data": json.dumps(self.EVENT),
            "channel": self.CHANNEL,
        }

        event = await event_bus.get_message(self.CHANNEL)
        assert event["data"] == self.EVENT["data"]
        event_bus.pubsub.get_message.assert_called_once()

    @pytest.mark.anyio
    async def test_get_no_message(self, event_bus: EventBus):
        event_bus.pubsub.get_message.return_value = None

        event = await event_bus.get_message(self.CHANNEL)
        assert not event
        event_bus.pubsub.get_message.assert_called_once()

    @pytest.mark.anyio
    async def test_get_message_invalid_payload(self, event_bus: EventBus):
        with patch(self.LOGGER_PATH) as logger:
            event_bus.pubsub.get_message.return_value = {
                "data": self.EVENT,
                "channel": self.CHANNEL,
            }

            await event_bus.get_message(self.CHANNEL)
            logger.error.assert_called_once_with("Invalid payload received!")

    @pytest.mark.anyio
    async def test_get_message_error(self, event_bus: EventBus):
        with patch(self.LOGGER_PATH) as logger, patch(self.SDK_PATH) as sdk:
            exc = Exception("Invalid type!")
            event_bus.pubsub.get_message.side_effect = exc

            await event_bus.get_message(self.CHANNEL)

            logger.error.assert_called_once_with(
                "Error occured while retrieving message from channel",
                extra={"channel": None},
            )

            sdk.capture_exception.assert_called_once_with(exc)
