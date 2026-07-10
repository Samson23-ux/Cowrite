from redis.asyncio import Redis
from redis import Redis as SyncRedis


class RedisRepository:
    def __init__(self, async_redis: Redis = None, sync_redis: SyncRedis = None):
        self._sync_redis = sync_redis
        self._async_redis = async_redis

    async def add_refresh_token(self, key: str, value: dict):
        await self._async_redis.hset(key, mapping=value)

    async def get_refresh_token(self, key: str) -> dict:
        return await self._async_redis.hgetall(key)

    async def delete_refresh_token(self, key: str):
        await self._async_redis.delete(key)
