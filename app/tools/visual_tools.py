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


@tool
async def describe_image(image_url: str) -> str:
    """
    Generate a text description of an image using Llama 4 Maverick Vision via Groq.
    
    This tool analyzes product images and generates concise descriptions
    optimized for semantic product search in Pinecone vector store.
    
    Args:
        image_url: Direct URL to the image (must be publicly accessible)
        
    Returns:
        Concise product description optimized for search
        (e.g., "Red matte lipstick with gold packaging", 
         "Black leather crossbody handbag with chain strap")
         
    Examples:
        >>> await describe_image("https://example.com/lipstick.jpg")
        "Red matte lipstick with metallic rose gold packaging"
    """
    print(f"\n>>> TOOL: describe_image called with URL: {image_url[:50]}...")
    logger.info(f"Describing image for visual search: {image_url}")
    
    if not settings.LLAMA_API_KEY:
        logger.error("LLAMA_API_KEY missing for image description")
        return "Error: Vision API not configured"

    try:
        # Llama 4 Vision on Groq - Use updated model name
        llm = ChatGroq(
            temperature=0.1,  # Low temperature for consistent descriptions
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="meta-llama/llama-4-maverick-17b-128e-instruct"  # Updated model
        )
        
        # Optimized prompt for product search
        prompt_text = """Describe this product image in a single sentence optimized for search.
        
Focus on:
- Product type (lipstick, dress, handbag, etc.)
- Key visual features (color, style, material)
- Distinguishing details (patterns, packaging, texture)

Output format: "[Product type] [color/style] [key features]"
Examples:
- "Red matte lipstick with gold metallic packaging"
- "Black leather crossbody handbag with chain strap"
- "Floral print midi dress with puff sleeves"

Be concise and specific."""
        
        # Convert image to format Llama Vision can accept
        # For local files, convert to base64 data URL
        if image_url.startswith(('http://', 'https://')):
            # Remote URL - use directly
            image_content = {"type": "image_url", "image_url": {"url": image_url}}
        else:
            # Local file - convert to base64
            print(f">>> TOOL: Converting local file to base64...")
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
            print(f">>> TOOL: Converted to base64 ({len(b64)} chars)")
        
        # Construct multimodal message
        msg = HumanMessage(content=[
            {"type": "text", "text": prompt_text},
            image_content
        ])
        
        print(f">>> TOOL: Calling Llama Vision API...")
        response = await llm.ainvoke([msg])
        description = response.content.strip()
        
        print(f">>> TOOL: Description generated: '{description[:100]}'")
        logger.info(f"Image description: '{description}'")
        
        return description
        
    except Exception as e:
        print(f">>> TOOL ERROR: Image description failed - {type(e).__name__}: {str(e)}")
        logger.error(f"Image description failed: {e}", exc_info=True)
        return "Error analyzing image"

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
    print(f"\n>>> TOOL: process_image_for_search called")
    logger.info(f"Generating DINOv2 embedding for: {image_url}")
    
    if not settings.HUGGINGFACE_API_KEY:
        logger.error("HUGGINGFACE_API_KEY missing")
        print(">>> TOOL ERROR: HuggingFace API key not configured")
        return []

    # Direct API call to HuggingFace (no InferenceClient)

    try:
        print(f">>> TOOL: Downloading/reading image...")
        
        # Handle both URLs and local file paths
        if image_url.startswith(('http://', 'https://')):
            # Remote URL - use requests
            img_response = requests.get(image_url, timeout=10)
            img_response.raise_for_status()
            image_bytes = img_response.content
            print(f">>> TOOL: Image downloaded from URL ({len(image_bytes)} bytes)")
        elif image_url.startswith('file://'):
            # file:// URL - strip protocol
            file_path = image_url.replace('file://', '')
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
            print(f">>> TOOL: Image read from file:// ({len(image_bytes)} bytes)")
        else:
            # Local path - read directly
            file_path = Path(image_url)
            if not file_path.exists():
                raise FileNotFoundError(f"Image file not found: {image_url}")
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
            print(f">>> TOOL: Image read from local path ({len(image_bytes)} bytes)")
        
        print(f">>> TOOL: Calling HuggingFace DINOv2 API directly...")
        
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
        
        print(f">>> TOOL: Raw response type: {type(embedding)}")
        
        # Normalize embedding format
        if isinstance(embedding, list):
            # Could be [[emb]] or [emb]
            if len(embedding) > 0:
                if isinstance(embedding[0], list):
                    # Nested list [[emb]] - take first
                    result = embedding[0]
                    print(f">>> TOOL: Embedding extracted from nested list (dims={len(result)})")
                elif isinstance(embedding[0], (int, float)):
                    # Direct list [emb]
                    result = embedding
                    print(f">>> TOOL: Embedding generated (dims={len(result)})")
                else:
                    print(f">>> TOOL WARNING: Unexpected embedding format")
                    result = []
            else:
                print(f">>> TOOL WARNING: Empty embedding list")
                result = []
        else:
            print(f">>> TOOL WARNING: Unexpected response: {type(embedding)}")
            result = []
        
        print(f">>> TOOL: Embedding generated (dims={len(result)})")
        logger.info(f"Embedding generated: {len(result)} dimensions")
        return result

    except requests.exceptions.Timeout:
        print(f">>> TOOL ERROR: HuggingFace API timeout")
        logger.error("DINOv2 API timeout")
        return []
    except requests.exceptions.HTTPError as e:
        print(f">>> TOOL ERROR: HTTP {e.response.status_code}")
        logger.error(f"DINOv2 API error: {e}")
        return []

    except Exception as e:
        print(f">>> TOOL ERROR: Visual embedding failed - {type(e).__name__}: {str(e)}")
        logger.error(f"Visual embedding failed: {e}", exc_info=True)
        return []
