import httpx
import os
import logging
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("logistics-client")

class TomTomClient:
    def __init__(self):
        self.api_key = os.getenv("TOMTOM_API_KEY", "")
        if not self.api_key:
            logger.error("TOMTOM_API_KEY is missing!")
            
        # Hardcoded Shop Origin (Iyaganku, Ibadan approx)
        # In a real system, this might be config-driven
        self.shop_lat = 7.3836892
        self.shop_lng = 3.8706751
        
    async def geocode_address(self, address: str) -> Dict[str, Any]:
        """
        Geocodes an address. Returns lat/lng and context.
        """
        if not self.api_key: return {"error": "API Key missing"}

        url = f"https://api.tomtom.com/search/2/search/{address}.json"
        params = {
            "key": self.api_key,
            "limit": 1,
            "countrySet": "NG"
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, params=params)
                data = resp.json()
                
                if not data.get("results"):
                    return {"error": "Address not found"}
                
                res = data["results"][0]
                pos = res["position"]
                addr = res["address"]
                
                is_in_ibadan = "Ibadan" in addr.get("municipality", "") or \
                               "Ibadan" in addr.get("freeformAddress", "") or \
                               "Ibadan" in address
                
                return {
                    "lat": pos["lat"],
                    "lng": pos["lon"],
                    "formatted_address": addr.get("freeformAddress"),
                    "is_in_ibadan": is_in_ibadan
                }
        except Exception as e:
            logger.error(f"Geocode Error: {e}")
            return {"error": str(e)}

    async def calculate_delivery_fee(self, destination: str) -> str:
        """
        Calculates delivery fee based on driving distance.
        Returns formatted string with fee details.
        """
        try:
            # 1. Geocode
            dest_data = await self.geocode_address(destination)
            if dest_data.get("error"):
                return f"Error: {dest_data['error']}"
            
            # 2. Check Region
            if not dest_data.get("is_in_ibadan"):
                 return "Fee: ₦1,500 (Flat Rate - Outside Ibadan)\nNote: Delivery 2-3 Days."

            # 3. Calculate Route
            d_lat, d_lng = dest_data["lat"], dest_data["lng"]
            
            route_url = f"https://api.tomtom.com/routing/1/calculateRoute/{self.shop_lat},{self.shop_lng}:{d_lat},{d_lng}/json"
            
            async with httpx.AsyncClient() as client:
                resp = await client.get(route_url, params={"key": self.api_key})
                data = resp.json()
                
                if "routes" not in data:
                    return "Error: Could not calculate route."
                
                route = data["routes"][0]
                dist_km = route["summary"]["lengthInMeters"] / 1000.0
                
                # Pricing Model
                fee = 1500 # Base
                if dist_km <= 8.7: fee = 1500
                elif dist_km < 12.2: fee = 2000
                elif dist_km < 13.1: fee = 2500
                else: fee = 3000
                
                return f"""Delivery Estimate:
- Distance: {dist_km:.2f} km
- Fee: ₦{fee:,.2f}
- Address: {dest_data.get('formatted_address')}
"""
        except Exception as e:
            logger.error(f"Routing Error: {e}")
            return f"Calculation Error: {str(e)}"
