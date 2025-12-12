from langchain.tools import tool
import httpx
from app.utils.config import settings
import logging

logger = logging.getLogger(__name__)

async def get_coordinates(address: str) -> dict:
    """Helper to geocode address using TomTom Fuzzy Search."""
    if not settings.TOMTOM_API_KEY:
        return {"error": "TomTom API Key missing"}
        
    url = f"https://api.tomtom.com/search/2/search/{address}.json"
    params = {
        "key": settings.TOMTOM_API_KEY,
        "limit": 1,
        "countrySet": "NG" # Restrict to Nigeria
    }
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, params=params)
            data = resp.json()
            
            if not data.get("results"):
                return {"error": "Address not found"}
                
            res = data["results"][0]
            pos = res["position"]
            addr = res["address"]
            
            # Context check for Ibadan
            is_in_ibadan = "Ibadan" in addr.get("municipality", "") or \
                           "Ibadan" in addr.get("freeformAddress", "") or \
                           "Ibadan" in address # Fallback check on query
                           
            return {
                "lat": pos["lat"],
                "lng": pos["lon"],
                "formatted_address": addr.get("freeformAddress"),
                "is_in_ibadan": is_in_ibadan
            }
        except Exception as e:
            logger.error(f"TomTom Geocode error: {e}")
            return {"error": str(e)}

@tool
async def geocode_address(address: str) -> dict:
    """
    Geocodes an address using TomTom API.
    Returns lat, lng, formatted_address, and is_in_ibadan status.
    """
    return await get_coordinates(address)

@tool
async def calculate_delivery_fee(destination_address: str) -> dict:
    """
    Calculates delivery fee based on driving distance from Shop to Customer in Ibadan using TomTom Routing API.
    PRICING:
    - Outside Ibadan: 1500 Flat
    - < 8.7km: 1500
    - 8.7 - 12.2km: 2000
    - 12.2 - 13.1km: 2500
    - > 13.1km: 3000
    """
    if not settings.TOMTOM_API_KEY:
        return {"error": "TomTom API Key missing"}

    origin_address = settings.SHOP_ADDRESS
    FEE_OUTSIDE_IBADAN = 1500
    
    try:
        # 1. Geocode Destination
        dest_coords = await get_coordinates(destination_address)
        if dest_coords.get("error"):
            return {"error": f"Invalid Destination: {dest_coords['error']}"}
            
        if not dest_coords.get("is_in_ibadan"):
             return {
                "distance_text": "Outside Ibadan",
                "distance_value_km": None,
                "fee": FEE_OUTSIDE_IBADAN,
                "currency": "NGN",
                "note": "Flat rate for outside Ibadan"
            }
            
        # 2. Geocode Origin (Shop) - Cached logic in real app, here fetch per call
        origin_coords = await get_coordinates(origin_address)
        if origin_coords.get("error"):
             # Fallback hardcoded coords for shop if geocode fails (Iyaganku approx)
             origin_coords = {"lat": 7.3836892, "lng": 3.8706751} 
        
        # 3. Calculate Route
        o_lat, o_lng = origin_coords["lat"], origin_coords["lng"]
        d_lat, d_lng = dest_coords["lat"], dest_coords["lng"]
        
        route_url = f"https://api.tomtom.com/routing/1/calculateRoute/{o_lat},{o_lng}:{d_lat},{d_lng}/json"
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(route_url, params={"key": settings.TOMTOM_API_KEY})
            data = resp.json()
            
            if "routes" not in data:
                return {"error": "Route calculation failed"}
                
            route = data["routes"][0]
            distance_meters = route["summary"]["lengthInMeters"]
            distance_km = distance_meters / 1000.0
            
            fee = 0
            # Pricing Logic
            if distance_km <= 8.7:
                fee = 1500
            elif 8.7 < distance_km < 12.2:
                fee = 2000
            elif 12.2 <= distance_km < 13.1:
                fee = 2500
            else:
                fee = 3000
                
            return {
                "distance_text": f"{distance_km:.2f} km",
                "distance_value_km": round(distance_km, 2),
                "fee": fee,
                "currency": "NGN"
            }

    except Exception as e:
        logger.error(f"Delivery Fee Calculation failed: {e}")
        return {"error": str(e)}
