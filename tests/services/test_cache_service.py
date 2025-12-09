import pytest
from app.services.cache_service import cache_service

@pytest.mark.asyncio
async def test_cache_set_get(mocker):
    # Mock generic redis client
    mock_redis = mocker.patch.object(cache_service, "redis", new_callable=mocker.AsyncMock)
    
    # Test Set
    await cache_service.set_json("test_key", {"a": 1})
    mock_redis.set.assert_called_once()
    
    # Test Get
    mock_redis.get.return_value = '{"a": 1}'
    result = await cache_service.get_json("test_key")
    assert result == {"a": 1}
    mock_redis.get.assert_called_with("test_key")
