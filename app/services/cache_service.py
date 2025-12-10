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
            url = None
            if self.redis_url:
                url = self.redis_url
                if not url.startswith("redis://") and not url.startswith("rediss://"):
                    url = f"redis://{url}"
            else:
                # Build URL from components, prefer TLS if port suggests TLS? (user can still force via REDIS_URL)
                url = f"redis://{self.host}:{self.port}/{self.db}"
            # Inject credentials if provided and not already present
            if "@" not in url and (self.user or self.pwd):
                prefix = "redis://"
                if url.startswith("rediss://"):
                    prefix = "rediss://"
                    host_part = url[len("rediss://"):]
                else:
                    host_part = url[len("redis://"):]
                user = self.user or "default"
                pwd = self.pwd or ""
                url = f"{prefix}{user}:{pwd}@{host_part}"
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
