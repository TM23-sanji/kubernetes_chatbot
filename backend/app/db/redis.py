import redis.asyncio as redis_async

from app.config import settings


class RedisManager:
    def __init__(self):
        self.client = None

    async def initialize(self):
        self.client = redis_async.Redis(
            url=settings.upstash_redis_rest_url,
            token=settings.upstash_redis_rest_token,
            decode_responses=True,
        )

    async def get(self, key: str) -> str | None:
        return await self.client.get(key)

    async def set(self, key: str, value: str, ttl: int = 3600):
        await self.client.set(key, value, ex=ttl)

    async def close(self):
        if self.client:
            await self.client.close()


redis_manager = RedisManager()
