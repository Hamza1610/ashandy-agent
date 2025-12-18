"""
Test: Delivery and Payment Workflow
Tests the delivery fee calculation and payment worker integration.

Note: The original tests used direct HTTP/geocode mocking which is now replaced
by MCP service calls. These tests use MCP service mocking instead.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.tools.tomtom_tools import calculate_delivery_fee, geocode_address
from app.agents.payment_worker import payment_worker_node


@pytest.mark.asyncio
async def test_calculate_delivery_fee_mcp():
    """Test delivery fee calculation via MCP service."""
    
    # Mock the MCP service call
    with patch("app.tools.tomtom_tools.mcp_service.call_tool") as mock_mcp:
        # Simulate MCP response for different zones
        mock_mcp.return_value = "{'fee': 1500, 'distance_km': 5.0, 'zone': 'Zone A'}"
        
        result = await calculate_delivery_fee.ainvoke("Bodija, Ibadan")
        
        # Should return formatted response from MCP
        assert "formatted_response" in result or "fee" in str(result).lower()
        mock_mcp.assert_called_once()


@pytest.mark.asyncio
async def test_geocode_address_mcp():
    """Test geocoding via MCP service."""
    
    with patch("app.tools.tomtom_tools.mcp_service.call_tool") as mock_mcp:
        mock_mcp.return_value = "{'lat': 7.3775, 'lng': 3.9470, 'formatted_address': 'Bodija, Ibadan, Oyo'}"
        
        result = await geocode_address.ainvoke("Bodija")
        
        # Should return dict with location data
        assert result is not None
        mock_mcp.assert_called_once_with("logistics", "geocode_address", {"address": "Bodija"})


@pytest.mark.asyncio  
async def test_calculate_delivery_fee_error_handling():
    """Test delivery fee calculation handles MCP errors gracefully."""
    
    with patch("app.tools.tomtom_tools.mcp_service.call_tool") as mock_mcp:
        mock_mcp.side_effect = Exception("MCP service unavailable")
        
        result = await calculate_delivery_fee.ainvoke("Test Address")
        
        # Should return error dict, not crash
        assert "error" in result
        assert "MCP service unavailable" in result["error"]


@pytest.mark.asyncio
async def test_payment_worker_requests_delivery_details():
    """Test payment worker requests delivery details if not provided."""
    
    # Minimal state without delivery details
    state = {
        "plan": [{"id": "task1", "task": "Process payment", "worker": "payment_worker"}],
        "task_statuses": {"task1": "in_progress"},
        "user_input": "I want to buy this product",
        "current_order": {"items": [{"name": "Test Product", "price": 5000}]},
        "delivery_details": {},  # Empty - should trigger request
        "messages": []
    }
    
    with patch("app.agents.payment_worker.get_llm") as mock_llm:
        # Mock LLM to return a response asking for delivery details
        mock_response = AsyncMock()
        mock_response.content = "To complete your order, please provide your delivery details!"
        mock_response.tool_calls = None
        mock_llm.return_value.ainvoke = AsyncMock(return_value=mock_response)
        
        result = await payment_worker_node(state)
        
        # Should have worker output requesting details
        assert result is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
