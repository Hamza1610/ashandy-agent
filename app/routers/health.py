from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.services.db_service import get_db
from app.utils.config import settings
import redis.asyncio as redis

router = APIRouter()

@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    health_status = {
        "status": "healthy",
        "services": {
            "db": "unknown",
            "redis": "unknown"
        }
    }

    # Check Database
    try:
        await db.execute(text("SELECT 1"))
        health_status["services"]["db"] = "up"
    except Exception as e:
        health_status["services"]["db"] = f"down: {str(e)}"
        health_status["status"] = "degraded"

    # Check Redis
    try:
        r = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
        await r.ping()
        await r.close()
        health_status["services"]["redis"] = "up"
    except Exception as e:
        health_status["services"]["redis"] = f"down: {str(e)}"
        health_status["status"] = "degraded"

    return health_status
