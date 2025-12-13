from langchain.tools import tool
from app.utils.config import settings
import requests
import logging
from io import BytesIO
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import asyncio
from pathlib import Path
import os
import base64

logger = logging.getLogger(__name__)


import json
import re

@tool
async def detect_product_from_image(image_url: str) -> dict:
    """
    Analyze product image to extract text, type, and visual details.
    
    Returns:
        dict: {
            "detected_text": "extracted text on package",
            "product_type": "lipstick/cream/etc",
            "visual_description": "detailed description",
            "confidence": 0.0-1.0
        }
    """
    logger.info(f"Analyzing product image details: {image_url}")
    
    if not settings.LLAMA_API_KEY:
        return {"error": "API Key missing"}

    try:
        llm = ChatGroq(
            temperature=0.1,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="meta-llama/llama-4-maverick-17b-128e-instruct"
        )
        
        prompt_text = """Analyze this product image carefully.
        
Tasks:
1. READ any text written on the packaging (Brand, Product Name, Flavor, Shade).
2. IDENTIFY the product type (e.g., Lipstick, Body Cream, Soap).
3. DESCRIBE visual features (Color, Texture, Shape).

Output strictly valid JSON:
{
  "detected_text": "Exact text found on image",
  "product_type": "Type",
  "visual_description": "Concise visual description",
  "confidence": 0.95
}
"""
        # Convert image to format Llama Vision can accept
        # For local files, convert to base64 data URL
        if image_url.startswith(('http://', 'https://')):
            # Remote URL - use directly
            image_content = {"type": "image_url", "image_url": {"url": image_url}}
        else:
            # Local file - convert to base64
            # Local file - convert to base64
            if image_url.startswith('file://'):
                file_path = image_url.replace('file://', '')
            else:
                file_path = image_url
            
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
            
            # Detect image format
            ext = Path(file_path).suffix.lower()
            mime_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.webp': 'image/webp',
                '.gif': 'image/gif'
            }.get(ext, 'image/jpeg')
            
            # Create base64 data URL
            b64 = base64.b64encode(image_bytes).decode('utf-8')
            data_url = f"data:{mime_type};base64,{b64}"
            image_content = {"type": "image_url", "image_url": {"url": data_url}}

        msg = HumanMessage(content=[
            {"type": "text", "text": prompt_text},
            image_content
        ])
        
        response = await llm.ainvoke([msg])
        content = response.content
        
        # Clean JSON
        json_str = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(json_str)
        
        logger.info(f"Detection Result: {data}")
        
        # --- ENHANCEMENT: Auto-Perform Vector Search ---
        try:
            logger.info("Auto-triggering visual vector search...")
            # 1. Get Embedding
            vector = await process_image_for_search.ainvoke(image_url)
            
            if vector:
                from app.services.mcp_service import mcp_service
                # 2. Search Knowledge Graph
                search_res = await mcp_service.call_tool("knowledge", "search_visual_memory", {"vector": vector})
                data["matched_products"] = search_res
            else:
                data["matched_products"] = "Could not generate vector for search."
                
        except Exception as ve:
             logger.error(f"Visual Search Auto-fail: {ve}")
             data["matched_products"] = "Search failed."
             
        return data

    except Exception as e:
        logger.error(f"Detection failed: {e}")
        return {"error": str(e), "detected_text": "", "visual_description": ""}

@tool
async def describe_image(image_url: str) -> str:
    """
    Legacy wrapper for backward compatibility. Returns string description.
    """
    data = await detect_product_from_image.ainvoke(image_url)
    if not data or "error" in data:
        return "Could not analyze image."
        
    desc = data.get("visual_description", "")
    text = data.get("detected_text", "")
    if text:
        return f"{desc} (Text on package: {text})"
    return desc

@tool
async def process_image_for_search(image_url: str) -> list:
    """
    Generate visual embedding from an image using HuggingFace DINOv2.
    
    This tool processes product images into 768-dimensional embedding vectors
    for visual similarity search in Pinecone vector database.
    
    Args:
        image_url: Direct URL to the image (must be publicly accessible)
        
    Returns:
        List of 768 floats representing the image embedding,
        or empty list if processing fails
        
    Technical Details:
        - Model: facebook/dinov2-base (768 dimensions)
        - API: HuggingFace Inference API
        - Use case: Visual product similarity search
        
    Examples:
        >>> embedding = await process_image_for_search("https://example.com/product.jpg")
        >>> len(embedding)
        768
    """
    logger.info(f"Generating DINOv2 embedding for: {image_url}")
    
    if not settings.HUGGINGFACE_API_KEY:
        logger.error("HUGGINGFACE_API_KEY missing")
        logger.error("HUGGINGFACE_API_KEY missing")
        return []

    # Direct API call to HuggingFace (no InferenceClient)

    try:
        # Handle both URLs and local file paths
        if image_url.startswith(('http://', 'https://')):
            # Remote URL - use requests
            img_response = requests.get(image_url, timeout=10)
            img_response.raise_for_status()
            image_bytes = img_response.content
        elif image_url.startswith('file://'):
            # file:// URL - strip protocol
            file_path = image_url.replace('file://', '')
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
        else:
            # Local path - read directly
            file_path = Path(image_url)
            if not file_path.exists():
                raise FileNotFoundError(f"Image file not found: {image_url}")
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
        
        # Use direct API call instead of InferenceClient
        api_url = "https://api-inference.huggingface.co/models/facebook/dinov2-base"
        headers = {
            "Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}",
            "Content-Type": "application/octet-stream"
        }
        
        # Make API request
        response = requests.post(api_url, headers=headers, data=image_bytes, timeout=30)
        response.raise_for_status()
        
        # Parse response - DINOv2 returns embeddings as list
        embedding = response.json()
        
        # Normalize embedding format
        if isinstance(embedding, list):
            # Could be [[emb]] or [emb]
            if len(embedding) > 0:
                if isinstance(embedding[0], list):
                    # Nested list [[emb]] - take first
                    result = embedding[0]
                elif isinstance(embedding[0], (int, float)):
                    # Direct list [emb]
                    result = embedding
                else:
                    logger.warning(f"Unexpected embedding format: {embedding}")
                    result = []
            else:
                logger.warning("Empty embedding list")
                result = []
        else:
                logger.warning(f"Unexpected response: {type(embedding)}")
                result = []
        
        logger.info(f"Embedding generated: {len(result)} dimensions")
        return result

    except requests.exceptions.Timeout:
        logger.error("DINOv2 API timeout")
        return []
    except requests.exceptions.HTTPError as e:
        logger.error(f"DINOv2 API error: {e}")
        return []

    except Exception as e:
        logger.error(f"Visual embedding failed: {e}", exc_info=True)
        return []
