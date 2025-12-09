from typing import TypedDict, Annotated, List, Dict, Optional, Any
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
import operator

class AgentState(TypedDict):
    # Core conversation
    messages: Annotated[List[BaseMessage], add_messages]
    user_id: str
    session_id: str
    platform: str  # "whatsapp" | "instagram"
    
    # Routing
    is_admin: bool
    query_type: str  # "text" | "image" | "admin_command"
    
    # Memory & context
    user_memory: Optional[Dict]  # From Pinecone
    cached_response: Optional[str]
    
    # Processing
    image_url: Optional[str]
    visual_matches: Optional[List[Dict]]
    product_recommendations: Optional[List[Dict]]
    
    # Order management
    order_intent: bool
    order_data: Optional[Dict]
    paystack_reference: Optional[str]
    
    # Sentiment & handoff
    sentiment_score: Optional[float]
    requires_handoff: bool
    
    # Admin
    admin_command: Optional[str]
    
    # Error handling
    error: Optional[str]
