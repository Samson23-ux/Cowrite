from typing import Optional
from redis.asyncio import Redis
from redis import Redis as SyncRedis


class RedisRepository:
    def __init__(self, async_redis: Redis = None, sync_redis: SyncRedis = None):
        self._sync_redis = sync_redis
        self._async_redis = async_redis

    async def create_hset(self, key: str, mapping: dict):
        await self._async_redis.hset(key, mapping=mapping)

    async def create_set(self, key: str, value: str):
        await self._async_redis.sadd(key, value)

    async def create_sorted_set(self, key: str, mapping: dict):
        await self._async_redis.zadd(key, mapping)

    async def increment_counter(self, key: str) -> int:
        return await self._async_redis.incr(key)

    async def set_key(self, key: str, value: str, expire: Optional[int] = None):
        await self._async_redis.set(key, value, ex=expire)

    async def reset_key_ttl(self, key: str, expire: int):
        await self._async_redis.expire(key, expire)

    async def get_key(self, key: str) -> str:
        return await self._async_redis.get(key)

    async def get_sorted_set(
        self, key: str, min: int = "-inf", max: int = "+inf", with_scores: bool = False
    ) -> list[tuple]:
        return await self._async_redis.zrangebyscore(
            key, min, max, withscores=with_scores
        )

    async def get_set(self, key: str) -> set[str]:
        return await self._async_redis.smembers(key)

    async def get_hset(self, key: str) -> dict:
        return await self._async_redis.hgetall(key)
    
    async def remove_set_member(self, key: str, value: str):
        await self._async_redis.srem(key, value)

    async def delete_key(self, key: str):
        await self._async_redis.delete(key)

    # sync

    def get_processed_email(self, key: str) -> str | None:
        return self._sync_redis.get(key)

    def mark_email_processed(self, key: str, value: str, ttl: int):
        self._sync_redis.set(key, value, ex=ttl)
