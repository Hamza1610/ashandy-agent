import pytest
import datetime
from unittest.mock import MagicMock
from app.tools.db_tools import check_admin_whitelist, get_product_details

# We need to mock AsyncSessionLocal used inside the tools.
# Since the tool imports it from app.services.db_service, we patch it there.

@pytest.mark.asyncio
async def test_check_admin_whitelist(mocker):
    mock_session = MagicMock()
    mock_execute_result = MagicMock()
    # Mock row as tuple/list-like
    mock_execute_result.fetchone.return_value = ('admin',) 
    mock_session.execute.return_value = mock_execute_result
    
    # Context manager mock
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    
    mocker.patch("app.tools.db_tools.AsyncSessionLocal", return_value=mock_session_ctx)
    
    result = await check_admin_whitelist.invoke("12345")
    assert result is True

@pytest.mark.asyncio
async def test_get_product_details(mocker):
    mock_session = MagicMock()
    mock_execute_result = MagicMock()
    
    # Mock product object
    MockProduct = MagicMock()
    MockProduct.name = "Test Product"
    MockProduct.sku = "SKU123"
    MockProduct.price = 5000
    MockProduct.description = "A test product"
    
    mock_execute_result.fetchall.return_value = [MockProduct]
    mock_session.execute.return_value = mock_execute_result
    
    mock_session_ctx = MagicMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None
    
    mocker.patch("app.tools.db_tools.AsyncSessionLocal", return_value=mock_session_ctx)
    
    result = await get_product_details.invoke("Test")
    assert "Test Product" in result
    assert "SKU123" in result
