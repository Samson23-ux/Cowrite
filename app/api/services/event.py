import json
import sentry_sdk
from redis.asyncio import Redis
from sentry_sdk import logger as sentry_logger


class EventBus:
    TIMEOUT = 0.1

    def __init__(self, async_redis: Redis):
        self._async_redis = async_redis

        # a single pubsub instance for the entire class
        self._async_pubsub = self._async_redis.pubsub()

    @property
    def pubsub(self):
        return self._async_pubsub

    @pubsub.setter
    def pubsub(self, pubsub):
        self._async_pubsub = pubsub

    @property
    def redis(self) -> Redis:
        return self._async_redis

    async def subscribe(self, channel: str):
        await self._async_pubsub.subscribe(channel)
        sentry_logger.info("Subscription completed!", extra={"channel": channel})

    async def unsubscribe(self, channel: str):
        await self._async_pubsub.unsubscribe(channel)
        sentry_logger.info("Unsubscribed from channel!", extra={"channel": channel})

    async def psubscribe(self, channel: str):
        await self._async_pubsub.psubscribe(channel)
        sentry_logger.info("Subscription completed!", extra={"channel": channel})

    async def punsubscribe(self, channel: str):
        await self._async_pubsub.punsubscribe(channel)
        sentry_logger.info("Unsubscribed from channel!", extra={"channel": channel})

    async def publish(self, channel: str, data: dict):
        try:
            message = json.dumps(data)
            await self._async_redis.publish(channel, message)
            sentry_logger.info(
                "Message published to channel!", extra={"channel": channel}
            )
        except TypeError:
            sentry_logger.error("Invalid payload received!")
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while publishing message to channel",
                extra={"channel": channel},
            )

    async def get_message(self, client_channel: str) -> dict | None:
        try:
            channel = None
            message = await self._async_pubsub.get_message(
                ignore_subscribe_messages=True, timeout=self.TIMEOUT
            )

            if message:
                data = message["data"]
                channel: str = message["channel"]
                event = json.loads(data)

                if channel == client_channel:
                    return event
                elif channel.startswith(client_channel):
                    return channel
            else:
                return
        except (json.JSONDecodeError, TypeError):
            sentry_logger.error("Invalid payload received!")
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while retrieving message from channel",
                extra={"channel": channel},
            )
