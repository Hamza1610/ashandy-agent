from langchain.tools import tool
from langchain_groq import ChatGroq
from app.utils.config import settings
import logging

logger = logging.getLogger(__name__)

@tool
async def analyze_sentiment(text: str) -> float:
    """
    Analyze sentiment of text using Llama 3 on Groq. 
    Returns score -1.0 (neg) to 1.0 (pos).
    """
    if not settings.LLAMA_API_KEY:
         logger.error("LLAMA_API_KEY (Groq) is missing.")
         return 0.0

    try:
        llm = ChatGroq(
            temperature=0,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="llama3-8b-8192"
        )
        
        system_prompt = """Analyze the sentiment of the following text. 
        Return ONLY a float number between -1.0 (extremely negative) and 1.0 (extremely positive). 
        Do not output any words, just the number."""
        
        messages = [
            ("system", system_prompt),
            ("human", text)
        ]
        
        response = await llm.ainvoke(messages)
        content = response.content.strip()
        
        # Try to parse float
        try:
            score = float(content)
            return max(min(score, 1.0), -1.0)
        except ValueError:
            logger.warning(f"Could not parse sentiment score from: {content}")
            return 0.0

    except Exception as e:
        logger.error(f"Sentiment analysis failed: {e}")
        return 0.0

