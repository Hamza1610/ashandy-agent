from langchain.tools import tool
from huggingface_hub import InferenceClient
from app.utils.config import settings
import requests
import logging
from io import BytesIO

logger = logging.getLogger(__name__)

@tool
async def process_image_for_search(image_url: str) -> list:
    """
    Get image embedding using HuggingFace InferenceClient (DINOv2).
    """
    if not settings.HUGGINGFACE_API_KEY:
        logger.error("HUGGINGFACE_API_KEY missing.")
        return []

    # Initialize Client (DINOv2 Base)
    # Using 'facebook/dinov2-base' as standard 768-dim model
    client = InferenceClient(
        model="facebook/dinov2-base",
        token=settings.HUGGINGFACE_API_KEY
    )

    try:
        # Fetch image bytes
        # Note: InferenceClient might support URLs depending on task/model, 
        # but sending bytes is robust.
        img_response = requests.get(image_url, timeout=10)
        img_response.raise_for_status()
        image_bytes = img_response.content
        
        # Use feature_extraction task helper
        # This handles the API call efficiently
        embedding = client.feature_extraction(image_bytes)
        
        # Result is typically a list (or ndarray if numpy installed, but usually list from API json)
        # Verify and return plain list
        if hasattr(embedding, "tolist"):
             return embedding.tolist()
        if isinstance(embedding, list):
             # Some models return [ [emb] ] or [emb]
             if len(embedding) > 0 and isinstance(embedding[0], list):
                 return embedding[0]
             return embedding
             
        return []

    except Exception as e:
        logger.error(f"Visual embedding failed via HF Client: {e}")
        return []

