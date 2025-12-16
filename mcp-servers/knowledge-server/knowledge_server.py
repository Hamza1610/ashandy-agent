import sys
from mcp.server.fastmcp import FastMCP
from src.vector_store import VectorStore
import logging
import json

# Initialize FastMCP Server
mcp = FastMCP("Ashandy Knowledge Server")

# Initialize Vector Store
try:
    vector_store = VectorStore()
except Exception as e:
    logging.error(f"Failed to initialize VectorStore: {e}")
    vector_store = None

@mcp.tool()
def search_products(query: str, top_k: int = 5) -> str:
    """Search for products using semantic search."""
    if not vector_store:
        return "Error: Vector store not initialized."
    return vector_store.search(query, top_k)

@mcp.tool()
def save_interaction(user_id: str, user_msg: str, ai_msg: str) -> str:
    """Save user interaction to memory."""
    if not vector_store:
        return "Error: Vector store not initialized."
    
    # Combine ensuring context is captured
    text = f"User: {user_msg}\nAI: {ai_msg}"
    return vector_store.save_interaction(user_id, text)

@mcp.tool()
def search_memory(query: str, user_id: str) -> str:
    """Search user's past interactions."""
    if not vector_store:
        return "Error: Vector store not initialized."
    return vector_store.search_memory_for_user(query, user_id)

@mcp.tool()
def analyze_and_enrich(image_url: str) -> str:
    """Analyze image and enrich (Placeholder for Visual Search)."""
    # This would typically call a visual model then vector_store.search_by_vector
    # ensuring we return a string description
    return "Visual search not fully implemented in this version yet."

if __name__ == "__main__":
    mcp.run(transport="stdio")
