import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.agents.delivery_agent import delivery_agent_node
from app.tools.tomtom_tools import calculate_delivery_fee, geocode_address
from app.models.agent_states import AgentState

@pytest.mark.asyncio
async def test_calculate_delivery_fee_tomtom_logic():
    """Test the pricing logic of the delivery fee calculator using TomTom logic."""
    
    # We mock 'get_coordinates' to return specific IDs for locations
    # We mock 'httpx' to return distances based on those IDs (coordinates)
    
    with patch("app.tools.tomtom_tools.get_coordinates") as mock_geo, \
         patch("app.tools.tomtom_tools.httpx.AsyncClient") as mock_client:
         
        # 1. Mock Geocoding
        async def side_effect_geo(address):
            if "Bodija" in address:
                return {"lat": 1.0, "lng": 1.0, "is_in_ibadan": True} # Bodija Coords
            elif "Akobo" in address:
                return {"lat": 2.0, "lng": 2.0, "is_in_ibadan": True} # Akobo Coords
            elif "Alakia" in address:
                return {"lat": 3.0, "lng": 3.0, "is_in_ibadan": True} # Alakia Coords
            elif "Iwo" in address:
                return {"lat": 4.0, "lng": 4.0, "is_in_ibadan": True} # Farther Coords
            else:
                return {"lat": 0.0, "lng": 0.0, "is_in_ibadan": True}
        
        mock_geo.side_effect = side_effect_geo
        
        # 2. Mock Routing HTTP Response
        mock_instance = mock_client.return_value
        mock_instance.__aenter__.return_value = mock_instance
        
        async def side_effect_get(url, params=None):
            dist_meters = 0
            # Check URL for coordinates
            # Bodija check (1.0)
            if "1.0,1.0" in url:
                dist_meters = 5000 # 5km
            # Akobo check (2.0)
            elif "2.0,2.0" in url:
                dist_meters = 10000 # 10km
            # Alakia check (3.0)
            elif "3.0,3.0" in url:
                dist_meters = 12500 # 12.5km
            # Iwo check (4.0)
            elif "4.0,4.0" in url:
                dist_meters = 15000 # 15km
                
            mock_resp = MagicMock()
            mock_resp.json.return_value = {
                "routes": [{"summary": {"lengthInMeters": dist_meters}}]
            }
            return mock_resp
            
        mock_instance.get.side_effect = side_effect_get
        
        # Test Cases
        # 1. Bodija (< 8.7km) -> 1500
        res = await calculate_delivery_fee.ainvoke("Bodija")
        assert res["fee"] == 1500
        
        # 2. Akobo (8.7 - 12.2km) -> 2000
        res = await calculate_delivery_fee.ainvoke("Akobo")
        assert res["fee"] == 2000
        
        # 3. Alakia (12.2 - 13.1km) -> 2500
        res = await calculate_delivery_fee.ainvoke("Alakia")
        assert res["fee"] == 2500
        
        # 4. Farther (> 13.1km) -> 3000
        res = await calculate_delivery_fee.ainvoke("Iwo Road")
        assert res["fee"] == 3000

@pytest.mark.asyncio
async def test_delivery_agent_node():
    """Test the Delivery Agent node logic."""
    state = {
        "delivery_details": {
            "address": "Bodija",
            "city": "Ibadan",
            "state": "Oyo"
        }
    }
    
    # Mock the tool call inside the agent
    # We patch the object where it is USED
    with patch("app.agents.delivery_agent.calculate_delivery_fee") as mock_tool:
        # Create a mock that has an .invoke method returning our dict
        mock_tool.invoke.return_value = {
            "fee": 1500,
            "distance_text": "5 km",
            "currency": "NGN"
        }
        
        result = await delivery_agent_node(state)
        
        assert result["delivery_fee"] == 1500
        assert result["error"] is None
