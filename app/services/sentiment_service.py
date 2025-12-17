"""
Sentiment Service: Analyzes message sentiment using keyword-based analysis.

Note: Previously used transformers/torch but switched to lightweight keyword approach
to avoid heavy dependencies. For advanced sentiment, consider using an MCP server.
"""
import logging

logger = logging.getLogger(__name__)


class SentimentService:
    """Lightweight keyword-based sentiment analysis service."""
    
    # Sentiment word lists
    POSITIVE_WORDS = {
        'thank', 'thanks', 'love', 'great', 'good', 'nice', 'excellent', 'happy', 
        'please', 'yes', 'perfect', 'amazing', 'wonderful', 'awesome', 'appreciate',
        'helpful', 'beautiful', 'best', 'fantastic', 'lovely'
    }
    
    NEGATIVE_WORDS = {
        'bad', 'terrible', 'hate', 'angry', 'upset', 'no', 'never', 'worst', 
        'scam', 'fraud', 'problem', 'issue', 'wrong', 'broken', 'disappointed',
        'horrible', 'awful', 'useless', 'waste', 'poor', 'annoyed', 'frustrated'
    }
    
    STRONG_POSITIVE = {'love', 'excellent', 'amazing', 'perfect', 'fantastic', 'awesome'}
    STRONG_NEGATIVE = {'hate', 'terrible', 'awful', 'scam', 'fraud', 'worst'}
    
    def analyze(self, text: str) -> float:
        """
        Analyze sentiment of text using keyword matching.
        
        Args:
            text: Message text to analyze
            
        Returns:
            Score from -1.0 (very negative) to 1.0 (very positive)
        """
        if not text or len(text.strip()) < 3:
            return 0.0  # Neutral for empty/very short
        
        text_lower = text.lower()
        
        # Count matches
        pos_count = sum(1 for word in self.POSITIVE_WORDS if word in text_lower)
        neg_count = sum(1 for word in self.NEGATIVE_WORDS if word in text_lower)
        
        # Weight strong words more
        strong_pos = sum(1 for word in self.STRONG_POSITIVE if word in text_lower)
        strong_neg = sum(1 for word in self.STRONG_NEGATIVE if word in text_lower)
        
        pos_score = pos_count + (strong_pos * 0.5)
        neg_score = neg_count + (strong_neg * 0.5)
        
        # Calculate final score
        if pos_score > neg_score:
            return min(0.5 + (pos_score * 0.1), 1.0)
        elif neg_score > pos_score:
            return max(-0.5 - (neg_score * 0.1), -1.0)
        return 0.0
    
    def classify_intent(self, text: str) -> str:
        """
        Classify user message intent.
        
        Returns: 'purchase', 'inquiry', 'complaint', 'greeting', 'other'
        """
        text_lower = text.lower()
        
        # Keyword-based classification
        # Include variations of purchase confirmation (I'll take, give me, yes, etc.)
        purchase_keywords = {'buy', 'order', 'want', 'get', 'purchase', 'pay', 'checkout', 'cart', 'deliver',
                            'take', 'give me', "i'll take", 'add to', 'yes', 'reserve', 'proceed'}
        inquiry_keywords = {'price', 'cost', 'stock', 'available', 'how much', 'do you have', 'what is', 'show me'}
        complaint_keywords = {'problem', 'issue', 'wrong', 'broken', 'refund', 'return', 'complaint', 'not working'}
        greeting_keywords = {'hi', 'hello', 'hey', 'good morning', 'good afternoon', 'good evening'}
        
        if any(kw in text_lower for kw in purchase_keywords):
            return 'purchase'
        elif any(kw in text_lower for kw in complaint_keywords):
            return 'complaint'
        elif any(kw in text_lower for kw in inquiry_keywords):
            return 'inquiry'
        elif any(kw in text_lower for kw in greeting_keywords):
            return 'greeting'
        else:
            return 'other'


# Singleton instance
sentiment_service = SentimentService()

