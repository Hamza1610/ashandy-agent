from langchain.tools import tool
from app.services.vector_service import vector_service
from app.utils.config import settings
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

# Load embedding model once (lazy loading pattern or global)
# Using a small, efficient model for CPU/production balance
try:
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
except Exception as e:
    logger.error(f"Failed to load SentenceTransformer: {e}")
    embedding_model = None

@tool
async def retrieve_user_memory(user_id: str) -> str:
    """Retrieve semantic memory/preferences for a user."""
    if not embedding_model:
        logger.error("Embedding model unavailable in retrieve_user_memory")
        return "Embedding model unavailable."
        
    logger.info(f"Retrieving memory for user_id: {user_id}")
    try:
        # Embed the query (user_id itself might not be semantic, ideally we query with context)
        # But commonly we query with "User preferences for <user_id>" or we list all vectors for user
        # Here we query for "preferences" essentially.
        query_vector = embedding_model.encode(f"User preferences for {user_id}").tolist()
        
        response = vector_service.query_vectors(
            index_name=settings.PINECONE_INDEX_USER_MEMORY,
            vector=query_vector,
            top_k=3,
            filter_metadata={"user_id": user_id}
        )
        
        matches = response.get("matches", [])
        if not matches:
            return "No previous memory found."
            
        memory_text = "\n".join([m['metadata'].get('memory_text', '') for m in matches])
        return f"User Context:\n{memory_text}"

    except Exception as e:
        logger.error(f"Error retrieving user memory: {e}")
        return "Error retrieving memory."

@tool
async def search_visual_products(vector: list) -> str:
    """
    Search for products using a visual embedding vector.
    Expects vector to be a list of floats (default 768 dim for DINO).
    """
    logger.info("Executing search_visual_products with vector input")
    try:
        response = vector_service.query_vectors(
            index_name=settings.PINECONE_INDEX_PRODUCTS,
            vector=vector,
            top_k=3
        )
        
        matches = response.get("matches", [])
        if not matches:
             return "No matching products found."

        result_str = "Visual Matches:\n"
        for m in matches:
            meta = m.get('metadata', {})
            result_str += f"- {meta.get('name')} (Price: {meta.get('price')})\n"
            
        return result_str
        
    except Exception as e:
        logger.error(f"Error searching visual products: {e}")
        return "Error executing visual search."

@tool
async def search_text_products(query: str) -> str:
    """
    Search for products using text description (Semantic Search).
    """
    if not embedding_model:
        logger.error("Embedding model unavailable in search_text_products")
        return "Embedding model unavailable."

    logger.info(f"Executing search_text_products with query: '{query}'")
    try:
        query_vector = embedding_model.encode(query).tolist()
        
        response = vector_service.query_vectors(
            index_name=settings.PINECONE_INDEX_PRODUCTS_TEXT,
            vector=query_vector,
            top_k=3
        )
        
        matches = response.get("matches", [])
        if not matches:
             return "No matching products found."

        result_str = "Semantic Matches:\n"
        for m in matches:
            meta = m.get('metadata', {})
            result_str += f"- {meta.get('name')} (Price: {meta.get('price')})\n"
            
        return result_str
        
    except Exception as e:
        logger.error(f"Error searching text products: {e}")
        return "Error executing text search."

@tool
async def save_user_interaction(user_id: str, user_msg: str, ai_msg: str) -> str:
    """
    Save a chat interaction (User + AI) to long-term memory.
    """
    if not embedding_model:
        logger.error("Embedding model unavailable in save_user_interaction")
        return "Embedding model unavailable."
        
    logger.info(f"Saving interaction for user_id: {user_id}")
    try:
        # Create a semantic representation of the turn
        text_to_embed = f"User: {user_msg}\nAI: {ai_msg}"
        vector = embedding_model.encode(text_to_embed).tolist()
        
        import time
        timestamp = time.time()
        
        # Upsert
        # ID strategy: user_id + timestamp
        vector_id = f"{user_id}_{int(timestamp)}"
        
        vector_data = [{
            "id": vector_id,
            "values": vector,
            "metadata": {
                "user_id": user_id,
                "memory_text": text_to_embed,
                "timestamp": timestamp,
                "type": "interaction"
            }
        }]
        
        vector_service.upsert_vectors(settings.PINECONE_INDEX_USER_MEMORY, vector_data)
        return "Interaction saved."
        
    except Exception as e:
        logger.error(f"Error saving memory: {e}")
        return "Failed to save memory."

