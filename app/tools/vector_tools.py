from langchain.tools import tool
from app.services.vector_service import vector_service
from app.utils.config import settings
from sentence_transformers import SentenceTransformer
import logging

logger = logging.getLogger(__name__)

# Lazy loader for embedding model
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            logger.info("Loading SentenceTransformer model...")
            _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            logger.error(f"Failed to load SentenceTransformer: {e}")
            return None
    return _embedding_model

@tool
async def retrieve_user_memory(user_id: str) -> str:
    """Retrieve semantic memory/preferences for a user."""
    embedding_model = get_embedding_model()
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


async def get_full_conversation_history(user_id: str, max_messages: int = 100):
    """
    Retrieve ALL conversation messages for a user from Pinecone.
    Returns list of LangChain message objects for full context.
    
    Args:
        user_id: User phone number or ID
        max_messages: Maximum messages to fetch (default 100 for unlimited)
    
    Returns:
        List of HumanMessage/AIMessage objects in chronological order
    """
    from langchain_core.messages import HumanMessage, AIMessage
    
    logger.info(f"Fetching full conversation history for {user_id} (max: {max_messages})")
    
    try:
        embedding_model = get_embedding_model()
        if not embedding_model:
            logger.warning("Embedding model unavailable, returning empty history")
            return []
        
        # Query for ALL user messages with high top_k
        query_vector = embedding_model.encode(f"Conversation history for {user_id}").tolist()
        
        response = vector_service.query_vectors(
            index_name=settings.PINECONE_INDEX_USER_MEMORY,
            vector=query_vector,
            top_k=max_messages,  # Fetch many messages
            filter_metadata={"user_id": user_id}
        )
        
        matches = response.get("matches", [])
        if not matches:
            logger.info(f"No conversation history found for {user_id}")
            return []
        
        logger.info(f"Found {len(matches)} messages for {user_id}")
        
        # Parse messages from metadata
        messages = []
        for match in matches:
            metadata = match.get('metadata', {})
            memory_text = metadata.get('memory_text', '')
            
            # Memory text format: "User: <msg>\nAssistant: <msg>"
            # Parse into separate messages
            if 'User:' in memory_text and 'Assistant:' in memory_text:
                parts = memory_text.split('\n')
                for part in parts:
                    if part.startswith('User:'):
                        content = part.replace('User:', '').strip()
                        if content:
                            messages.append(HumanMessage(content=content))
                    elif part.startswith('Assistant:'):
                        content = part.replace('Assistant:', '').strip()
                        if content:
                            messages.append(AIMessage(content=content))
        
        # Messages are in reverse chronological order from Pinecone
        # Reverse to get chronological order
        messages.reverse()
        
        logger.info(f"Parsed {len(messages)} individual messages from {len(matches)} memory entries")
        return messages
        
    except Exception as e:
        logger.error(f"Error fetching conversation history: {e}", exc_info=True)
        return []

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
    embedding_model = get_embedding_model()
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

async def save_user_interaction(user_id: str, user_msg: str, ai_msg: str) -> str:
    """
    Save a chat interaction (User + AI) to long-term memory.
    This is a normal async function (not a LangChain tool) since it's called directly from workflows.
    """
    if not user_id or not user_msg or not ai_msg:
        logger.warning(f"Missing required fields: user_id={bool(user_id)}, user_msg={bool(user_msg)}, ai_msg={bool(ai_msg)}")
        return "Missing required fields for memory save."
    
    embedding_model = get_embedding_model()
    if not embedding_model:
        logger.error("Embedding model unavailable in save_user_interaction")
        return "Embedding model unavailable."
        
    logger.info(f"Saving interaction for user_id: {user_id}, user_msg length: {len(user_msg)}, ai_msg length: {len(ai_msg)}")
    try:
        # Create a semantic representation of the turn
        text_to_embed = f"User: {user_msg}\nAI: {ai_msg}"
        logger.debug(f"Text to embed (first 100 chars): {text_to_embed[:100]}")
        
        vector = embedding_model.encode(text_to_embed).tolist()
        logger.debug(f"Generated vector of dimension: {len(vector)}")
        
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
        
        logger.info(f"Calling upsert_vectors with index: {settings.PINECONE_INDEX_USER_MEMORY}, vector_id: {vector_id}")
        vector_service.upsert_vectors(settings.PINECONE_INDEX_USER_MEMORY, vector_data)
        logger.info(f"Successfully saved interaction to Pinecone: {vector_id}")
        return f"Interaction saved to Pinecone (ID: {vector_id})."
        
    except Exception as e:
        logger.error(f"Error saving memory: {e}", exc_info=True)
        return f"Failed to save memory: {str(e)}"

