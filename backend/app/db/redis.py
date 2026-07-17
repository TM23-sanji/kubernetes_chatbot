import json

import httpx

from app.config import settings


class RedisManager:
    def __init__(self):
        self.client = None

    async def initialize(self):
        self.client = httpx.AsyncClient(
            base_url=settings.upstash_redis_rest_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {settings.upstash_redis_rest_token}",
            },
        )

    async def get(self, key: str) -> str | None:
        try:
            resp = await self.client.post("/", content=json.dumps(["GET", key]))
            if resp.status_code != 200:
                return None
            parsed = resp.json()
            if isinstance(parsed, dict) and "result" in parsed:
                return parsed["result"]
            return resp.text.strip() or None
        except Exception:
            return None

    async def set(self, key: str, value: str, ttl: int = 3600):
        try:
            await self.client.post(
                "/", content=json.dumps(["SET", key, value, "EX", str(ttl)])
            )
        except Exception:
            pass

    async def close(self):
        if self.client:
            await self.client.aclose()


redis_manager = RedisManager()
