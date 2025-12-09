import pytest
from app.tools.vector_tools import retrieve_user_memory, search_visual_products
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_retrieve_user_memory(mocker):
    # Mock embedding model
    mock_model = MagicMock()
    mock_model.encode.return_value.tolist.return_value = [0.1] * 384
    mocker.patch("app.tools.vector_tools.embedding_model", mock_model)
    
    # Mock vector service
    mock_service = mocker.patch("app.tools.vector_tools.vector_service")
    mock_service.query_vectors.return_value = {
        "matches": [{"metadata": {"memory_text": "Likes organic stuff"}}]
    }
    
    result = await retrieve_user_memory.invoke("user123")
    assert "Likes organic stuff" in result

@pytest.mark.asyncio
async def test_search_visual_products(mocker):
    mock_service = mocker.patch("app.tools.vector_tools.vector_service")
    mock_service.query_vectors.return_value = {
        "matches": [{"metadata": {"name": "Visual Product", "price": 200}}]
    }
    
    result = await search_visual_products.invoke([0.1]*768)
    assert "Visual Product" in result
