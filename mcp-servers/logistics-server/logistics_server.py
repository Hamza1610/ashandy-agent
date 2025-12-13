from mcp.server.fastmcp import FastMCP
from src.tomtom_client import TomTomClient
import logging

# Initialize Server
mcp = FastMCP("ashandy-logistics")
client = TomTomClient()

@mcp.tool()
async def geocode_address(address: str) -> str:
    """
    Get coordinates and context for an address (Nigeria).
    Returns formatted string.
    """
    res = await client.geocode_address(address)
    return str(res)

@mcp.tool()
async def calculate_delivery_fees(destination: str) -> str:
    """
    Calculate delivery fee from Ashandy Shop (Ibadan) to Destination.
    """
    return await client.calculate_delivery_fee(destination)

if __name__ == "__main__":
    mcp.run()
