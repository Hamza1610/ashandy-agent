import pytest
import asyncio
from unittest.mock import MagicMock
from app.utils.config import settings

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_settings(mocker):
    mocker.patch.object(settings, 'PINECONE_API_KEY', 'mock_pinecone_key')
    mocker.patch.object(settings, 'PAYSTACK_SECRET_KEY', 'mock_paystack_key')
    mocker.patch.object(settings, 'META_WHATSAPP_TOKEN', 'mock_wa_token')
    mocker.patch.object(settings, 'LLAMA_API_KEY', 'mock_llama_key')
    return settings

@pytest.fixture
def mock_db_session():
    mock_session = MagicMock()
    # Setup standard async mock returns
    return mock_session
