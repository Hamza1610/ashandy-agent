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
        logger.warning("LLAMA_API_KEY (Groq) is missing; defaulting to safe.")
        return "safe"
        
    try:
        llm = ChatGroq(
            temperature=0, 
            groq_api_key=settings.LLAMA_API_KEY, 
            model_name="meta-llama/llama-guard-4-12b"
        )
        
        system_prompt = """You are a safety classifier for customer support chat.
Return exactly one token: 'safe' or 'unsafe'.

Definition of unsafe:
- violence, self-harm, hate, harassment, sexual content involving minors, explicit sexual content, crime, malware, fraud, extremist content, medical or financial advice that could harm, doxxing, phishing, or any intent to cause harm.
- explicit PII collection requests (asking for passwords, OTPs, credit card numbers).

Definition of safe:
- Greetings, product questions, pricing, availability, delivery, support, or other benign content.

Rules:
- Reply ONLY 'safe' or 'unsafe'. No punctuation or extra text.
- If unsure, reply 'safe'. Do not over-block normal commerce/sales queries.
"""
        
        messages = [
            ("system", system_prompt),
            ("human", query),
        ]
        
        response = await llm.ainvoke(messages)
        result = response.content.strip().lower()
        
        if result == "unsafe":
            return "unsafe"
        return "safe"

    except Exception as e:
        logger.error(f"Llama Guard check failed: {e}")
        return "safe" # Prefer not to block due to infra errors

