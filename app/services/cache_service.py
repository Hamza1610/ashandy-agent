import redis.asyncio as redis
from app.utils.config import settings
import logging
import json

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self):
        self.redis_url = settings.REDIS_URL
        self.ttl = settings.REDIS_CACHE_TTL
        self.redis = None

    async def connect(self):
         if not self.redis:
            url = self.redis_url
            if not url.startswith("redis://") and not url.startswith("rediss://"):
                url = f"redis://{url}"
            self.redis = redis.from_url(url, encoding="utf-8", decode_responses=True)

    async def get_json(self, key: str):
        await self.connect()
        try:
            data = await self.redis.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set_json(self, key: str, value: dict, ttl: int = None):
        await self.connect()
        try:
            await self.redis.set(key, json.dumps(value), ex=ttl or self.ttl)
        except Exception as e:
             logger.error(f"Redis set error: {e}")

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
