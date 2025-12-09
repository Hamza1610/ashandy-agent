from langchain.tools import tool
from langchain_groq import ChatGroq
from app.utils.config import settings
import logging

logger = logging.getLogger(__name__)

@tool
async def check_safety(query: str) -> str:
    """
    Check if a query is safe using Llama Guard (via Groq).
    Returns 'safe' or 'unsafe'.
    """
    if not settings.LLAMA_API_KEY:
        logger.error("LLAMA_API_KEY (Groq) is missing.")
        return "unsafe" # Default to unsafe if we can't check
        
    try:
        # Use a model appropriate for safety, e.g., llama3-70b-8192 or specific guard if available on Groq
        # Groq hosts Llama 3. We will prompt it to act as Llama Guard.
        llm = ChatGroq(
            temperature=0, 
            groq_api_key=settings.LLAMA_API_KEY, 
            model_name="llama3-70b-8192"
        )
        
        system_prompt = """You are a safety classification system. 
        Analyze the user's message for any toxic, harmful, illegal, or dangerous content. 
        If the message is harmful, respond with 'unsafe'. 
        If it is effectively safe, respond with 'safe'. 
        Do not provide explanations, only the single word classification."""
        
        messages = [
            ("system", system_prompt),
            ("human", query),
        ]
        
        response = await llm.ainvoke(messages)
        result = response.content.strip().lower()
        
        if "unsafe" in result:
            return "unsafe"
        return "safe"

    except Exception as e:
        logger.error(f"Llama Guard check failed: {e}")
        return "unsafe" # Fail closed

