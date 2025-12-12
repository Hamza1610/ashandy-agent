"""
Instagram Analysis Tools
Helper functions to analyze Instagram posts for product inventory.
"""
from langchain_groq import ChatGroq
from app.utils.config import settings
from langchain_core.messages import HumanMessage
import logging
import json
import re

logger = logging.getLogger(__name__)

async def analyze_instagram_post(image_url: str, caption: str) -> dict:
    """
    Analyze an Instagram post (Image + Caption) to extract product details.
    
    Returns:
        dict: {
            "is_product": bool,
            "name": str,
            "price": float,
            "description": str,
            "confidence": float
        }
        or None if analysis fails.
    """
    if not settings.LLAMA_API_KEY:
        logger.error("LLM API Key missing.")
        return None

    try:
        # Llama 4 Vision
        llm = ChatGroq(
            temperature=0.1,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="meta-llama/llama-4-maverick-17b-128e-instruct"
        )
        
        prompt = f"""Analyze this Instagram post to identify if it is selling a cosmetic product.

Context (Caption): "{caption}"

Task:
1. Determine if this image shows a product for sale (Cosmetics/Accessories).
2. Extract the Name, generic Price (in Naira), and a simplified Description from the caption and image.
3. If price is missing in caption, estimate 0.
4. If it's a selfie/meme/random photo, set is_product=false.

Output MUST be valid JSON only:
{{
  "is_product": true/false,
  "name": "Product Name",
  "price": 5000,
  "description": "Visual description + sales details",
  "confidence": 0.9
}}
"""
        
        # Multimodal Input
        if image_url:
            msg = HumanMessage(content=[
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ])
        else:
            msg = HumanMessage(content=prompt) # Just caption analysis if image fails?
            
        logger.info(f"Analyzing IG Post: {caption[:30]}...")
        response = await llm.ainvoke([msg])
        content = response.content
        
        # Cleaning JSON markdown if present
        json_str = content.replace("```json", "").replace("```", "").strip()
        data = json.loads(json_str)
        
        return data

    except Exception as e:
        logger.error(f"IG Analysis Failed: {e}")
        return None
