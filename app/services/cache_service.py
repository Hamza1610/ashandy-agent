"""
Cache Service: Redis caching with JSON serialization.
"""
import redis.asyncio as redis
from app.utils.config import settings
import logging
import json

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.host = settings.REDIS_HOST
        self.port = settings.REDIS_PORT
        self.db = settings.REDIS_DB
        self.user = settings.REDIS_USERNAME
        self.pwd = settings.REDIS_PASSWORD
        self.ttl = settings.REDIS_CACHE_TTL
        self.redis = None

    async def connect(self):
        if not self.redis:
            url = self.redis_url or f"redis://{self.host}:{self.port}/{self.db}"
            if not url.startswith(("redis://", "rediss://")):
                url = f"redis://{url}"
            
            if "@" not in url and (self.user or self.pwd):
                prefix = "rediss://" if url.startswith("rediss://") else "redis://"
                host_part = url[len(prefix):]
                url = f"{prefix}{self.user or 'default'}:{self.pwd or ''}@{host_part}"
            
            self.redis = redis.from_url(url, encoding="utf-8", decode_responses=True)

    async def get(self, key: str):
        await self.connect()
        try:
            return await self.redis.get(key)
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: str, expire: int = None):
        await self.connect()
        try:
            await self.redis.set(key, value, ex=expire or self.ttl)
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    async def get_json(self, key: str):
        data = await self.get(key)
        return json.loads(data) if data else None

    async def set_json(self, key: str, value: dict, ttl: int = None):
        await self.set(key, json.dumps(value), expire=ttl)

    async def delete(self, key: str):
        await self.connect()
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")

    async def flush(self):
        await self.connect()
        try:
            await self.redis.flushdb()
        except Exception as e:
            logger.error(f"Redis flush error: {e}")


cache_service = CacheService()
