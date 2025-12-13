import httpx
import os
import logging
from typing import List, Dict, Any

# Configure logging locally for the server
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pos-client")

class PHPPOSClient:
    def __init__(self):
        self.base_url = os.getenv("PHPPOS_BASE_URL", "http://localhost/phppos")
        self.api_key = os.getenv("POS_CONNECTOR_API_KEY", "")
        self.headers = {
            "accept": "application/json",
            "x-api-key": self.api_key,
            "User-Agent": "Ashandy-MCP-Server/1.0"
        }

    async def search_items(self, query: str) -> str:
        """
        Search for items in PHPPOS by name or ID.
        Returns a formatted string for the Agent.
        """
        url = f"{self.base_url}/items"
        logger.info(f"Searching POS: {url} with query '{query}'")
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=self.headers)
                
                if response.status_code != 200:
                    logger.error(f"POS Error {response.status_code}: {response.text}")
                    # Fallback for dev/demo if needed
                    # return self._get_mock_data(query) 
                    return f"Error connecting to POS: {response.status_code}"

                items = response.json()
                
                # Filter Logic (Same as original tool)
                matches = []
                query_lower = query.lower()
                
                for item in items:
                    name = item.get("name", "").lower()
                    if query_lower in name or query_lower == str(item.get("item_id")):
                        matches.append(item)
                        if len(matches) >= 5:
                            break
                
                if not matches:
                    return f"No matching products found for '{query}'."

                # Format Logic
                result_str = ""
                for m in matches:
                    # Defensive extract
                    locs = m.get("locations", {})
                    # Just grab first location found or "1"
                    qty = "N/A"
                    if locs:
                         first_loc = list(locs.values())[0]
                         if isinstance(first_loc, dict):
                             qty = first_loc.get("quantity", "N/A")
                    
                    price = m.get("unit_price", 0)
                    try:
                        price = int(float(price))
                    except:
                        pass

                    result_str += f"""
- ID: {m.get('item_id')}
  Name: {m.get('name')}
  Price: ₦{price:,}
  Stock: {qty}
  Desc: {m.get('description', 'N/A')}
"""
                return result_str

        except Exception as e:
            logger.error(f"POS Client Exception: {e}")
            return self._get_mock_data(query)

    def _get_mock_data(self, query: str) -> str:
        """Fallback mock data for development."""
        return """
[MOCK POS DATA - LIVE CONNECTION FAILED]
- ID: 999
  Name: Nivea Body Lotion (Mock)
  Price: ₦4,500
  Stock: 15
  Desc: Deep moisture for dry skin.
"""
