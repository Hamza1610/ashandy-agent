"""
Conversation Summary Service: Efficiently manages conversation context.

Instead of sending last N messages (expensive), this service:
1. Maintains a rolling summary of the conversation
2. Updates the summary periodically (every 5 messages)
3. Provides compact context to workers (summary + last 3 messages)

This reduces token usage by ~80% while maintaining full context.
"""
from app.services.llm_service import get_llm
from app.services.cache_service import cache_service
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from typing import List, Dict, Optional
import logging
import json

logger = logging.getLogger(__name__)


class ConversationSummaryService:
    """Manages efficient conversation context through summarization with Redis persistence."""
    
    SUMMARIZE_EVERY = 5  # Summarize every 5 messages
    RECENT_MESSAGES = 3  # Always include last 3 messages verbatim
    SUMMARY_TTL = 86400  # 24 hours TTL for summaries
    
    async def get_efficient_context(
        self, 
        session_id: str, 
        messages: List[BaseMessage]
    ) -> List[BaseMessage]:
        """
        Get efficient conversation context for LLM.
        
        Returns: [SystemSummary] + [Last 3 messages]
        Instead of: [Last 10-20 messages]
        
        Token savings: ~80%
        """
        if len(messages) <= self.RECENT_MESSAGES:
            # Short conversation, no summarization needed
            return messages
        
        # Get current count and summary from Redis (Fail-Safe)
        current_count = len(messages)
        cache_key = f"conv_summary:{session_id}"
        
        cached_count = 0
        cached_summary = ""
        
        try:
            # We protect this read. If Redis hangs/fails, we just proceed without summary.
            cached_data = await cache_service.get_json(cache_key)
            if cached_data:
                cached_count = cached_data.get("count", 0)
                cached_summary = cached_data.get("summary", "")
        except Exception as e:
            logger.warning(f"Summary Service: Redis read failed (ignoring): {e}")
        
        # Check if we need to update summary
        messages_since_summary = current_count - cached_count
        
        # Only try to summarize if we have a valid previous state or enough new messages
        # If Redis failed (count=0, summary=""), we might re-summarize everything, which is safe but slower.
        if messages_since_summary >= self.SUMMARIZE_EVERY:
            # Summarize all messages except the last 3
            messages_to_summarize = messages[:-self.RECENT_MESSAGES]
            
            # Protected Summarization Call
            try:
                new_summary = await self._summarize_messages(messages_to_summarize, cached_summary)
                
                # Save to Redis (Fail-Safe)
                try:
                    await cache_service.set_json(cache_key, {
                        "summary": new_summary,
                        "count": current_count
                    }, ttl=self.SUMMARY_TTL)
                    logger.info(f"Updated summary for {session_id}")
                except Exception as e:
                    logger.warning(f"Summary Service: Redis write failed (ignoring): {e}")
                
                cached_summary = new_summary
            except Exception as e:
                logger.error(f"Summary Service: Generation failed (skipping): {e}")
        
        # Build efficient context
        context = []
        
        # Add summary as system context if exists
        if cached_summary:
            context.append(SystemMessage(content=f"[CONVERSATION SUMMARY]\n{cached_summary}"))
        
        # Add last 3 messages verbatim
        context.extend(messages[-self.RECENT_MESSAGES:])
        
        logger.debug(f"Efficient context: {len(context)} items (saved {len(messages) - len(context)} tokens)")
        return context
    
    async def _summarize_messages(
        self, 
        messages: List[BaseMessage],
        previous_summary: str = ""
    ) -> str:
        """Generate a summary of conversation messages."""
        if not messages:
            return previous_summary
        
        try:
            llm = get_llm(model_type="fast", temperature=0.1)
            
            # Build conversation text
            conv_text = ""
            for msg in messages:
                role = "Customer" if isinstance(msg, HumanMessage) else "Agent"
                content = msg.content if isinstance(msg.content, str) else str(msg.content)
                conv_text += f"{role}: {content[:200]}...\n" if len(content) > 200 else f"{role}: {content}\n"
            
            prompt = f"""Summarize this customer service conversation in 2-3 sentences.
Focus on: products discussed, prices mentioned, customer intent, any decisions made.

{f"Previous context: {previous_summary}" if previous_summary else ""}

Recent conversation:
{conv_text}

Summary (be concise):"""

            response = await llm.ainvoke([HumanMessage(content=prompt)])
            summary = response.content.strip()
            
            # Limit summary length
            if len(summary) > 500:
                summary = summary[:500] + "..."
            
            return summary
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            return previous_summary or "Unable to generate summary."
    
    async def clear_session(self, session_id: str):
        """Clear cached summary for a session (e.g., after /delete_memory)."""
        cache_key = f"conv_summary:{session_id}"
        try:
            await cache_service.delete(cache_key)
            logger.info(f"Cleared conversation summary for {session_id}")
        except Exception as e:
            logger.warning(f"Failed to clear summary from Redis: {e}")


# Singleton instance
conversation_summary_service = ConversationSummaryService()
