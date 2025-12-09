from langchain.tools import tool
from app.services.cache_service import cache_service

@tool
async def check_semantic_cache(query_hash: str) -> str:
    """Check Redis for a cached response to a query."""
    result = await cache_service.get_json(query_hash)
    if result:
        return result.get("response")
    return None

@tool
async def update_semantic_cache(query_hash: str, response: str):
    """Update Redis cache with a new query-response pair."""
    await cache_service.set_json(query_hash, {"response": response})
