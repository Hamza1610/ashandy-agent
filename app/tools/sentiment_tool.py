"""
Sentiment Tool: Analyze text sentiment with fallback.
"""
from langchain.tools import tool
from app.services.llm_service import invoke_with_fallback
import logging

logger = logging.getLogger(__name__)


@tool
async def analyze_sentiment(text: str) -> float:
    """Analyze sentiment with fallback. Returns -1.0 (negative) to 1.0 (positive)."""
    try:
        response = await invoke_with_fallback(
            messages=[
                ("system", "Return ONLY a float -1.0 to 1.0 for sentiment. No words."),
                ("user", text)
            ],
            model_type="fast",
            temperature=0
        )
        
        try:
            score = float(response.strip())
            return max(min(score, 1.0), -1.0)
        except ValueError:
            logger.warning(f"Could not parse: {response}")
            return 0.0

    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        return 0.0
