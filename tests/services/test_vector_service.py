import pytest
from app.services.vector_service import VectorService
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_vector_service_init(mocker, mock_settings):
    # Mock Pinecone class
    mock_pinecone = mocker.patch("app.services.vector_service.Pinecone")
    mocker.patch("app.services.vector_service.ServerlessSpec") # Mock spec
    
    service = VectorService()
    
    # Assert initialization tried to create indexes
    assert service.pc is not None
    # We can check if create_index was called or list_indexes was called
    # This depends on exact internal logic of _ensure_index_exists calling upon init
    # Given the implementation, it calls _ensure_index_exists for both indexes.
    
    # Verify mock interaction
    mock_pinecone.return_value.list_indexes.assert_called()

@pytest.mark.asyncio
async def test_upsert_vectors(mocker):
    mock_pc = MagicMock()
    mock_index = MagicMock()
    mock_pc.Index.return_value = mock_index
    
    service = VectorService()
    service.pc = mock_pc
    
    vectors = [{"id": "1", "values": [0.1]*384}]
    service.upsert_vectors("test-index", vectors)
    
    mock_pc.Index.assert_called_with("test-index")
    mock_index.upsert.assert_called_with(vectors=vectors)
