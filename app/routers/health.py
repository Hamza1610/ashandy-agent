"""
Health Router: System health checks for DB, Redis, and LLM providers.
"""
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.services.db_service import get_db
from app.utils.config import settings
import redis.asyncio as redis

router = APIRouter()


@router.get("/health")
async def health_check(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """
    Check core services: database and Redis.
    Returns 503 if app is still initializing (Readiness Probe).
    """
    # Readiness Check
    if not getattr(request.app.state, "is_ready", False):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "initializing", "message": "Application is starting up"}

    health_status = {"status": "healthy", "services": {"db": "unknown", "redis": "unknown"}}

    try:
        await db.execute(text("SELECT 1"))
        health_status["services"]["db"] = "up"
    except Exception as e:
        health_status["services"]["db"] = f"down: {str(e)}"
        health_status["status"] = "degraded"

    try:
        r = redis.from_url(settings.REDIS_URL or f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", 
                          encoding="utf-8", decode_responses=True)
        await r.ping()
        await r.close()
        health_status["services"]["redis"] = "up"
    except Exception as e:
        health_status["services"]["redis"] = f"down: {str(e)}"
        health_status["status"] = "degraded"

    return health_status


@router.get("/health/llm")
async def llm_health_check():
    """Check LLM provider availability and failover status."""
    from app.services.llm_service import llm_service
    
    providers_status = await llm_service.health_check()
    
    # Determine overall status
    up_count = sum(1 for v in providers_status.values() if v == "up")
    
    if up_count == 0:
        overall = "critical"
    elif up_count < len(providers_status):
        overall = "degraded"
    else:
        overall = "healthy"
    
    return {
        "status": overall,
        "providers": providers_status,
        "primary": "groq",
        "fallback_chain": ["groq", "together", "openrouter"],
        "failure_counts": {p.value: c for p, c in llm_service.failure_counts.items()}
    }


@router.post("/health/llm/reset")
async def reset_llm_failures():
    """Reset LLM failure counts (admin action)."""
    from app.services.llm_service import llm_service
    llm_service.reset_failure_counts()
    return {"status": "ok", "message": "Failure counts reset"}


@router.get("/health/mcp")
async def mcp_health_check():
    """Check MCP server connection status."""
    from app.services.mcp_service import mcp_service
    
    mcp_status = await mcp_service.get_health_status()
    
    # Determine overall status
    connected = sum(1 for v in mcp_status.values() if v.get("status") == "connected")
    total = len(mcp_status)
    
    if connected == 0:
        overall = "critical"
    elif connected < total:
        overall = "degraded"
    else:
        overall = "healthy"
    
    return {
        "status": overall,
        "servers": mcp_status,
        "connected": connected,
        "total": total
    }


@router.get("/health/keys")
async def key_rotation_status():
    """Check API key rotation status for all services."""
    from app.services.key_rotation_service import key_rotation_service
    
    status = key_rotation_service.get_rotation_status()
    
    # Count services with pending rotations
    pending = sum(1 for s in status.values() if s.get("next_key_pending"))
    configured = sum(1 for s in status.values() if s.get("configured"))
    
    return {
        "status": "rotation_pending" if pending > 0 else "ok",
        "services": status,
        "configured": configured,
        "pending_rotations": pending,
        "message": f"{pending} key(s) pending rotation" if pending > 0 else "All keys current"
    }
