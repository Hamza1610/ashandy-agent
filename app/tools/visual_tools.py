from langchain.tools import tool
from huggingface_hub import InferenceClient
from app.utils.config import settings
import requests
import logging
from io import BytesIO
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import asyncio

logger = logging.getLogger(__name__)

# Using generic InferenceClient for DINOv2
hf_client = InferenceClient(token=settings.HUGGINGFACE_API_KEY)

@tool
async def describe_image(image_url: str) -> str:
    """
    Generate a text description of an image using Llama 3.2 Vision via Groq.
    Useful for semantic search of products based on an uploaded image.
    """
    if not settings.LLAMA_API_KEY:
        return "LLM API Key missing."

    try:
        # Llama 3.2 Vision on Groq
        llm = ChatGroq(
            temperature=0.1,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="llama-3.2-11b-vision-preview" 
        )
        
        # Construct multimodal message
        msg = HumanMessage(content=[
            {"type": "text", "text": "Describe the main object in this image briefly for product search. e.g. 'Red floral dress', 'Black leather handbag'."},
            {"type": "image_url", "image_url": {"url": image_url}}
        ])
        
        response = await llm.ainvoke([msg])
        return response.content
        
    except Exception as e:
        logger.error(f"Image description failed: {e}")
        return ""

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

