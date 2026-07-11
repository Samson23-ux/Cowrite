import json
import asyncio
import sentry_sdk
from redis.asyncio import Redis
from sentry_sdk import logger as sentry_logger


class EventBus:
    TIMEOUT = 30

    def __init__(self, redis: Redis):
        self._redis = redis
        self._pubsub = (
            self._redis.pubsub()
        )  # a single pubsub instance for the entire class

    @property
    def pubsub(self):
        return self._pubsub

    @pubsub.setter
    def pubsub(self, pubsub):
        self._pubsub = pubsub

    @property
    def redis(self) -> Redis:
        return self._redis

    async def subscribe(self, channel: str):
        await self._pubsub.subscribe(channel)
        sentry_logger.info("Subscription completed!", extra={"channel": channel})

    async def unsubscribe(self, channel: str):
        if not self._pubsub:
            return

        await self._pubsub.unsubscribe(channel)
        sentry_logger.info("Unsubscribed from channel!", extra={"channel": channel})

    async def publish(self, channel: str, data: dict):
        try:
            message = json.dumps(data)
            self._redis.publish(channel, message)
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

    async def get_message(self) -> dict | None:
        try:
            message = asyncio.wait_for(
                self._pubsub.get_message(ignore_subscribe_messages=True),
                timeout=self.TIMEOUT,
            )

            if message:
                data = message["data"]
                channel: str = message["channel"]
                event = json.loads(data)

                return event
            else:
                return
        except asyncio.TimeoutError, asyncio.CancelledError:
            return
        except json.JSONDecodeError:
            sentry_logger.error("Invalid payload received!")
        except Exception as exc:
            sentry_sdk.capture_exception(exc)
            sentry_logger.error(
                "Error occured while retrieving message from channel",
                extra={"channel": channel},
            )
