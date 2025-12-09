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
        return "Embedding model unavailable."
        
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

