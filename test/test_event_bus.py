import uuid
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


from app.api.services.event import EventBus


@pytest.fixture
async def event_bus() -> EventBus:
    redis = AsyncMock()
    pubsub = AsyncMock()

    eb = EventBus(redis=redis)
    eb.TIMEOUT = 3
    eb.pubsub = pubsub

    return eb


class TestEventBus:
    CHANNEL = "test:channel"
    EVENT = {"data": "test"}
    SDK_PATH = "app.api.services.event.sentry_sdk"
    LOGGER_PATH = "app.api.services.event.sentry_logger"

    @pytest.mark.asyncio
    async def test_subscribe(self, event_bus):
        event_bus.pubsub.subscribe = AsyncMock(return_value=None)
        await event_bus.subscribe(self.CHANNEL)

        event_bus.pubsub.subscribe.assert_awaited_once_with(self.CHANNEL)

    @pytest.mark.asyncio
    async def test_unsubscribe(self, event_bus):
        await event_bus.subscribe(self.CHANNEL)

        event_bus.pubsub.unsubscribe = AsyncMock(return_value=None)
        await event_bus.unsubscribe(self.CHANNEL)

        event_bus.pubsub.unsubscribe.assert_awaited_once_with(self.CHANNEL)

    @pytest.mark.asyncio
    async def test_unsubscribe_no_subpub(self, event_bus):
        await event_bus.subscribe(self.CHANNEL)

        event_bus.pubsub = None

        event_bus.pubsub.unsubscribe = AsyncMock(return_value=None)
        await event_bus.unsubscribe(self.CHANNEL)

        event_bus.pubsub.unsubscribe.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_publish_message(self, event_bus):
        await event_bus.publish(self.CHANNEL, self.EVENT)
        event_bus.redis.assert_called_once_with(self.CHANNEL, self.EVENT)

    @pytest.mark.asyncio
    async def test_publish_message_invalid_type(self, event_bus):
        with patch(self.LOGGER_PATH) as logger:
            logger.error = MagicMock(return_value=None)

            await event_bus.publish(self.CHANNEL, {"id": uuid.uuid4()})
            logger.error.assert_called_once_with("Invalid payload received!")

    @pytest.mark.asyncio
    async def test_publish_message_error(self, event_bus):
        with patch(self.LOGGER_PATH) as logger, patch(self.SDK_PATH) as sdk:
            logger.error = MagicMock(return_value=None)
            sdk.capture_exception = MagicMock(return_value=None)

            exc = Exception("Invalid type!")
            event_bus.redis.publish.side_effects = exc
            await event_bus.publish(self.CHANNEL, self.EVENT)

            logger.error.assert_called_once_with(
                "Error occured while publishing message to channel",
                extra={"channel": self.CHANNEL},
            )

            sdk.assert_called_once_with(exc)

    @pytest.mark.asyncio
    async def test_get_message(self, event_bus):
        message_json = json.dumps(self.EVENT)
        event_bus.pubsub.get_message.return_value = {"data": message_json}

        event = await event_bus.get_message()
        assert event["data"] == self.EVENT["data"]
        event_bus.pubsub.get_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_no_message(self, event_bus):
        message_json = json.dumps(self.EVENT)
        event_bus.pubsub.get_message.return_value = None

        event = await event_bus.get_message()
        assert not event
        event_bus.pubsub.get_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_timeout_message(self, event_bus):
        # message_json = json.dumps(self.EVENT)
        # event_bus.pubsub.get_message.return_value = {"data": message_json}

        event = await event_bus.get_message()
        assert not event
        event_bus.pubsub.get_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_message_invalid_payload(self, event_bus):
        with patch(self.LOGGER_PATH) as logger:
            event_bus.pubsub.get_message.return_value = {"data": b""}

            await event_bus.get_message()
            logger.error.assert_called_once_with("Invalid payload received!")

    @pytest.mark.asyncio
    async def test_get_message_error(self, event_bus):
        with patch(self.LOGGER_PATH) as logger, patch(self.SDK_PATH) as sdk:
            exc = Exception("Invalid type!")
            event_bus.pubsub.get_message.side_effects = exc

            await event_bus.get_message()

            logger.error.assert_called_once_with(
                "Error occured while retrieving message from channel",
                extra={"channel": self.CHANNEL},
            )

            sdk.assert_called_once_with(exc)
