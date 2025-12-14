"""
Instagram Tools: Analyze Instagram posts for product inventory.
"""
from langchain_core.messages import HumanMessage
from app.services.llm_service import get_llm
import logging
import json

logger = logging.getLogger(__name__)


async def analyze_instagram_post(image_url: str, caption: str) -> dict:
    """
    Analyze Instagram post to extract product details.
    Returns: {is_product, name, price, description, confidence} or None.
    """
    try:
        llm = get_llm(model_type="powerful", temperature=0.1)
        
        prompt = f"""Analyze this Instagram post. Caption: "{caption}"

Determine if it shows a product for sale. Extract name, price (Naira), description.
If selfie/meme, set is_product=false.

Output JSON: {{"is_product": true, "name": "...", "price": 5000, "description": "...", "confidence": 0.9}}"""
        
        if image_url:
            msg = HumanMessage(content=[{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_url}}])
        else:
            msg = HumanMessage(content=prompt)
            
        logger.info(f"Analyzing IG: {caption[:30]}...")
        response = await llm.ainvoke([msg])
        json_str = response.content.replace("```json", "").replace("```", "").strip()
        return json.loads(json_str)

    except Exception as e:
        logger.error(f"IG Analysis Failed: {e}")
        return None
