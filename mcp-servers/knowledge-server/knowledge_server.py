from mcp.server.fastmcp import FastMCP
from src.vector_store import VectorStore
import logging

# Initialize Server
mcp = FastMCP("ashandy-knowledge")
store = VectorStore() # Loads model instantly

@mcp.tool()
async def search_memory(query: str) -> str:
    """
    Search Pinecone for relevant products or memories.
    """
    return store.search(query)

@mcp.tool()
async def upsert_memory(text: str) -> str:
    """
    Store a new memory/fact into Pinecone.
    """
    # Simple dummy metadata for now
    return store.upsert_text(text, {"source": "user_memory"})

@mcp.tool()
async def upsert_product(name: str, description: str, price: float, source: str, image_url: str, permalink: str, item_id: str) -> str:
    """
    Store a product in the Knowledge Graph.
    """
    # Create the text context for embedding
    text_context = f"{name}. {description}"
    
    # Construct Metadata
    metadata = {
        "name": name,
        "price": price,
        "description": description,
        "source": source,
        "image_url": image_url,
        "permalink": permalink,
        "item_id": item_id,
        "text": text_context
    }
    
    # ID Strategy: match original logic "ig_txt_{id}"
    # Wait, original logic made TWO embeddings: visual and text.
    # Knowledge Server currently focuses on TEXT upsert.
    # Visual upsert requires passing a VECTOR.
    # For now, let's just handle the TEXT component via MCP.
    # If Visual search is needed, we need to pass the vector or do image processing on the server.
    # The server has SentenceTransformers (Text). It probably doesn't have the CLIP/DINO model for Vision unless we added it.
    # Let's stick to Text Search for now as it's the primary agent tool.
    
    vector_id = f"ig_txt_{item_id}"
    return store.upsert_text(text_context, metadata, id=vector_id)

@mcp.tool()
async def upsert_vector_data(vector: list, metadata: dict, id: str) -> str:
    """
    Store pre-computed vector (e.g. Visual Embedding) in Knowledge Graph.
    """
    return store.upsert_vector(vector, metadata, id=id)

@mcp.tool()
async def search_visual_memory(vector: list) -> str:
    """
    Search Knowledge Graph using a visual embedding vector.
    """
    return store.search_by_vector(vector)

@mcp.tool()
async def search_user_context(user_id: str, query: str) -> str:
    """
    Search for past user interactions/context.
    """
    return store.search_memory_for_user(query, user_id)

@mcp.tool()
async def save_interaction(user_id: str, text: str) -> str:
    """
    Save a new user interaction to memory.
    """
    return store.save_interaction(user_id, text)

if __name__ == "__main__":
    mcp.run()
