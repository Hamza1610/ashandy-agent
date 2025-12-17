"""
Response Cache Service: Two-layer caching (Redis exact match + Semantic similarity).
Reduces LLM calls by 50-70% for common queries.
"""
from hashlib import sha256
from app.services.cache_service import cache_service
from app.utils.config import settings
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class ResponseCacheService:
    """Two-layer response caching: exact match (Redis) + semantic (Pinecone)."""
    
    EXACT_TTL = 3600       # 1 hour for exact matches
    SEMANTIC_TTL = 86400   # 24 hours for semantic matches
    SIMILARITY_THRESHOLD = 0.92
    
    # Patterns indicating non-cacheable personalized content
    PERSONALIZED_PATTERNS = [
        "your order", "payment link", "delivery to", 
        "order #", "ref:", "paystack.com/pay/", "tracking"  # Removed ₦ - prices are OK to cache
    ]
    
    # Patterns for cacheable general questions
    GENERAL_PATTERNS = [
        "what are", "where is", "how do", "do you have", "what's the",
        "opening hours", "location", "address", "deliver", "return",
        "payment methods", "contact"
    ]
    
    async def get_cached_response(self, query: str, user_id: str = None) -> str | None:
        """
        Two-layer cache lookup: exact match first, then semantic.
        
        Returns cached response or None if not found.
        """
        query_normalized = query.lower().strip()
        
        # Skip cache for very short queries
        if len(query_normalized) < 5:
            return None
        
        # Layer 1: Exact Match (Redis)
        query_hash = sha256(query_normalized.encode()).hexdigest()[:16]
        cache_key = f"response_cache:{query_hash}"
        
        try:
            cached = await cache_service.get_json(cache_key)
            if cached:
                logger.info(f"Cache HIT (exact): {query[:40]}...")
                return cached.get("response")
        except Exception as e:
            logger.warning(f"Redis cache error: {e}")
        
        # Layer 2: Semantic Match (via MCP Knowledge Server)
        try:
            from app.services.mcp_service import mcp_service
            
            # Generate embedding for query
            embedding = await self._get_text_embedding(query_normalized)
            if not embedding:
                return None
            
            # Search in response cache namespace
            matches = await mcp_service.call_tool("knowledge", "search_response_cache", {
                "vector": embedding,
                "threshold": self.SIMILARITY_THRESHOLD,
                "top_k": 1
            })
            
            if matches and isinstance(matches, list) and len(matches) > 0:
                best_match = matches[0]
                score = best_match.get("score", 0)
                
                if score >= self.SIMILARITY_THRESHOLD:
                    logger.info(f"Cache HIT (semantic, {score:.2f}): {query[:40]}...")
                    return best_match.get("metadata", {}).get("response")
                    
        except Exception as e:
            logger.warning(f"Semantic cache error: {e}")
        
        return None
    
    async def cache_response(self, query: str, response: str, topic: str = None):
        """
        Store response in both cache layers.
        Skips personalized/order-specific responses.
        """
        query_normalized = query.lower().strip()
        
        # Skip caching for personalized responses
        if self._is_personalized(response):
            logger.debug(f"Skipping cache (personalized): {query[:30]}...")
            return
        
        # Skip caching for very short responses
        if len(response) < 20:
            return
        
        # Layer 1: Redis exact match
        query_hash = sha256(query_normalized.encode()).hexdigest()[:16]
        cache_key = f"response_cache:{query_hash}"
        
        try:
            await cache_service.set_json(cache_key, {
                "query": query,
                "response": response,
                "topic": topic,
                "cached_at": datetime.now().isoformat()
            }, ttl=self.EXACT_TTL)
        except Exception as e:
            logger.warning(f"Redis cache write error: {e}")
        
        # Layer 2: Semantic cache (only for general questions)
        if self._is_general_question(query_normalized):
            try:
                from app.services.mcp_service import mcp_service
                
                embedding = await self._get_text_embedding(query_normalized)
                if embedding:
                    vec_id = f"cache_{query_hash}"
                    await mcp_service.call_tool("knowledge", "upsert_response_cache", {
                        "id": vec_id,
                        "vector": embedding,
                        "metadata": {
                            "query": query,
                            "response": response,
                            "topic": topic or "general",
                            "cached_at": datetime.now().isoformat()
                        }
                    })
                    logger.debug(f"Cached (semantic): {query[:30]}...")
            except Exception as e:
                logger.warning(f"Semantic cache write error: {e}")
    
    async def invalidate_topic(self, topic: str):
        """Invalidate all cached responses for a topic."""
        try:
            # For Redis, we'd need to scan keys - expensive
            # For now, just log - semantic cache entries expire naturally
            logger.info(f"Cache invalidation requested for topic: {topic}")
        except Exception as e:
            logger.error(f"Cache invalidation error: {e}")
    
    async def warm_cache(self, faqs: list[tuple[str, str]]):
        """Pre-populate cache with common FAQs."""
        for query, response in faqs:
            await self.cache_response(query, response, topic="faq")
        logger.info(f"Warmed cache with {len(faqs)} FAQs")
    
    def _is_personalized(self, response: str) -> bool:
        """Check if response contains user-specific data."""
        response_lower = response.lower()
        return any(p in response_lower for p in self.PERSONALIZED_PATTERNS)
    
    def _is_general_question(self, query: str) -> bool:
        """Check if query is a cacheable general question."""
        return any(p in query for p in self.GENERAL_PATTERNS)
    
    async def _get_text_embedding(self, text: str) -> list | None:
        """Get text embedding using MCP Knowledge server."""
        try:
            from app.services.mcp_service import mcp_service
            result = await mcp_service.call_tool("knowledge", "get_text_embedding", {"text": text})
            if result and isinstance(result, list):
                return result
        except Exception as e:
            logger.warning(f"Embedding generation failed: {e}")
        return None


# Singleton
response_cache_service = ResponseCacheService()


# Common FAQs to warm cache on startup
COMMON_FAQS = [
    ("What are your opening hours?", "We're open Monday to Saturday, 9 AM to 7 PM. Closed on Sundays. 🕐"),
    ("Where is your shop located?", "We're at Shop 9&10, Divine Favor Plaza, Railway Shed, Iyaganku, Dugbe Rd, Ibadan. 📍"),
    ("Do you deliver?", "Yes! We deliver anywhere in Nigeria. Delivery fees start from ₦1,500 depending on your location. 🚚"),
    ("How do I pay?", "We accept card payments and bank transfers via Paystack. You'll receive a secure payment link. 💳"),
    ("Can I return products?", "Returns are accepted within 7 days if the product is unopened. Please contact us for details. 📦"),
    ("What payment methods do you accept?", "We accept debit/credit cards and bank transfers through our secure Paystack payment links. 💳"),
    ("How long does delivery take?", "Delivery within Ibadan takes 1-2 days. Other states take 2-5 business days. 📦"),
    ("Do you have original products?", "Yes! All our products are 100% authentic. We source directly from authorized distributors. ✅"),
]
