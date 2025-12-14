"""
Visual Tools: Image analysis, product detection, and visual similarity search.
Uses Llama Vision for OCR/detection and DINOv2 for embeddings.
"""
from langchain.tools import tool
from app.utils.config import settings
from app.services.mcp_service import mcp_service
from app.services.llm_service import get_llm
from langchain_core.messages import HumanMessage
from pathlib import Path
import requests
import logging
import base64
import json

logger = logging.getLogger(__name__)


@tool
async def detect_product_from_image(image_url: str) -> dict:
    """Analyze product image to extract text, type, and visual details."""
    logger.info(f"Analyzing: {image_url}")
    
    try:
        llm = get_llm(model_type="powerful", temperature=0.1)
        
        prompt = """Analyze this product image. Tasks:
1. READ text on packaging (Brand, Product Name, Shade)
2. IDENTIFY product type (Lipstick, Cream, Soap)
3. DESCRIBE visual features

Output JSON: {"detected_text": "...", "product_type": "...", "visual_description": "...", "confidence": 0.95}"""

        if image_url.startswith(('http://', 'https://')):
            image_content = {"type": "image_url", "image_url": {"url": image_url}}
        else:
            file_path = image_url.replace('file://', '') if image_url.startswith('file://') else image_url
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
            ext = Path(file_path).suffix.lower()
            mime_type = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp'}.get(ext, 'image/jpeg')
            b64 = base64.b64encode(image_bytes).decode('utf-8')
            image_content = {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}"}}

        response = await llm.ainvoke([HumanMessage(content=[{"type": "text", "text": prompt}, image_content])])
        json_str = response.content.replace("```json", "").replace("```", "").strip()
        data = json.loads(json_str)
        logger.info(f"Detection: {data}")
        
        # Auto vector search
        try:
            vector = await process_image_for_search.ainvoke(image_url)
            if vector:
                data["matched_products"] = await mcp_service.call_tool("knowledge", "search_visual_memory", {"vector": vector})
            else:
                data["matched_products"] = "Could not generate vector."
        except Exception as e:
            logger.error(f"Visual search failed: {e}")
            data["matched_products"] = "Search failed."
              
        return data

    except Exception as e:
        logger.error(f"Detection failed: {e}")
        return {"error": str(e), "detected_text": "", "visual_description": ""}


@tool
async def describe_image(image_url: str) -> str:
    """Legacy wrapper for backward compatibility."""
    data = await detect_product_from_image.ainvoke(image_url)
    if not data or "error" in data:
        return "Could not analyze image."
    desc = data.get("visual_description", "")
    text = data.get("detected_text", "")
    return f"{desc} (Text: {text})" if text else desc


@tool
async def process_image_for_search(image_url: str) -> list:
    """Generate 768-dim DINOv2 visual embedding for similarity search."""
    logger.info(f"Generating embedding: {image_url}")
    
    if not settings.HUGGINGFACE_API_KEY:
        logger.error("HUGGINGFACE_API_KEY missing")
        return []

    try:
        if image_url.startswith(('http://', 'https://')):
            img_response = requests.get(image_url, timeout=10)
            img_response.raise_for_status()
            image_bytes = img_response.content
        else:
            file_path = image_url.replace('file://', '') if image_url.startswith('file://') else image_url
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
        
        response = requests.post(
            "https://api-inference.huggingface.co/models/facebook/dinov2-base",
            headers={"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}", "Content-Type": "application/octet-stream"},
            data=image_bytes,
            timeout=30
        )
        response.raise_for_status()
        embedding = response.json()
        
        if isinstance(embedding, list) and len(embedding) > 0:
            result = embedding[0] if isinstance(embedding[0], list) else embedding
        else:
            result = []
        
        logger.info(f"Embedding: {len(result)} dimensions")
        return result

    except requests.exceptions.Timeout:
        logger.error("DINOv2 API timeout")
        return []
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        return []
