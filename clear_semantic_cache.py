"""
Quick script to clear the semantic cache so we can test the new tool execution.
Run this before testing to ensure cache doesn't interfere.
"""
import asyncio
import sys
sys.path.insert(0, '.')

async def clear_cache():
    from app.services.cache_service import cache_service
    
    print("Clearing semantic cache...")
    
    try:
        # Try to flush all keys
        if hasattr(cache_service, 'redis'):
            await cache_service.redis.flushdb()
            print("✅ Redis cache cleared!")
        elif hasattr(cache_service, 'clear'):
            await cache_service.clear()
            print("✅ Cache cleared!")
        else:
            print("⚠️  Cache service doesn't have a clear method")
            print("   Cache data stored in:", type(cache_service))
            
    except Exception as e:
        print(f"❌ Error clearing cache: {e}")
        print("   You may need to restart the cache service manually")

if __name__ == "__main__":
    asyncio.run(clear_cache())
    print("\nNow send a WhatsApp message to test!")
