"""
Clean, unified state schema for the Awelewa agent system.
This follows strict typing and consistent naming conventions.
"""
from typing import TypedDict, Annotated, List, Dict, Optional, Literal
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
import operator


def replace_dict(left: Optional[Dict], right: Optional[Dict]) -> Optional[Dict]:
    """Replacement reducer: new dict completely replaces old dict.
    Used for task_statuses and retry_counts to prevent stale state."""
    if right is not None:
        return right
    return left if left is not None else {}


class AgentState(TypedDict):
    """
    Unified state schema for all agents in the system.
    
    Design Principles:
    - Single source of truth for all state keys
    - Strict typing with Literal for enums
    - No duplicate or inconsistent keys
    - All optional fields explicitly marked
    """
    
    # ========== Core Conversation ==========
    messages: Annotated[List[BaseMessage], add_messages]
    """Conversation history with automatic message accumulation"""
    
    user_id: str
    """User identifier (WhatsApp phone number or Instagram ID)"""
    
    session_id: str
    """Session identifier for conversation tracking"""
    
    platform: Literal["whatsapp", "instagram"]
    """Platform the message originated from"""
    
    # ========== Routing ==========
    is_admin: bool
    """Whether the user is an admin (whitelisted)"""
    
    query_type: Literal["admin", "text", "image"]
    """Type of query being processed"""
    
    # ========== Safety ==========
    blocked: bool
    """Whether the message was blocked by safety checks"""
    
    # ========== Supervisor ==========
    supervisor_verdict: Optional[Literal["safe", "block", "ignore", "cached"]]
    """Verdict from input supervisor: safe, block, ignore, or cached"""
    
    # ========== Memory & Context ==========
    user_memory: Optional[Dict]
    """User preferences and history from Pinecone vector store"""
    
    cached_response: Optional[str]
    """Cached response from Redis semantic cache"""
    
    query_hash: Optional[str]
    """Hash of the current query for cache operations"""
    
    last_user_message: Optional[str]
    """The original user message text for memory saving"""
    
    # ========== Visual Search ==========
    image_url: Optional[str]
    """URL of uploaded image for visual search"""
    
    visual_context: Optional[Dict]
    """Visual search results from SAM + DINOv3"""
    
    visual_matches: Optional[List[Dict]]
    """Product matches from visual search"""
    
    # ========== Sales & Products ==========
    product_recommendations: Optional[List[Dict]]
    """Product recommendations from sales agent"""
    
    # ========== Order Management ==========
    order_intent: bool
    """Whether user has purchase intent"""
    
    order: Optional[Dict]
    """Order details (items, amount, email, etc.)"""
    
    order_data: Optional[Dict]
    """Alternative key for order details (backward compatibility)"""
    
    paystack_reference: Optional[str]
    """Paystack payment reference ID"""
    
    ordered_items: Optional[List[Dict]]
    """List of items customer has chosen to purchase"""
    
    customer_email: Optional[str]
    """Customer's email address for payment"""
    
    # ========== Sentiment & Handoff ==========
    sentiment_score: Optional[float]
    """Sentiment score from analysis (-1.0 to 1.0)"""
    
    requires_handoff: bool
    """Whether conversation requires human handoff"""
    
    # ========== Admin ==========
    admin_command: Optional[str]
    """Admin command string (e.g., /stock, /report)"""
    
    # ========== Error Handling ==========
    error: Optional[str]
    """Error message if any step fails"""
    
    # ========== Planning & Execution ==========
    plan: Optional[List[Dict]]
    """List of tasks to execute"""
    
    current_step_index: Optional[int]
    """Index of the current task being executed"""

    worker_result: Optional[str]
    """Result from the last worker execution"""

    planner_thought: Optional[str]
    """Chain-of-thought reasoning from the planner agent"""

    conflict_resolution: Optional[str]
    """Result from conflict resolver when multiple workers have outputs"""

    # ========== System 2.0: Pub/Sub & Review ==========
    task_statuses: Annotated[Optional[Dict[str, str]], replace_dict]
    """Status of each task ID: pending, in_progress, reviewing, approved, failed.
    Uses replace_dict reducer to prevent stale states from persisting."""

    retry_counts: Annotated[Optional[Dict[str, int]], replace_dict]
    """Number of retries for each task ID.
    Uses replace_dict reducer to prevent stale retry counts from persisting."""

    reviewer_critique: Optional[str]
    """Feedback from the Reviewer agent for the current task"""

    supervisor_output_verdict: Optional[str]
    """Verdict from the Output Supervisor"""

    worker_outputs: Annotated[Dict[str, str], operator.or_]
    """Map of task_id -> worker output string. Merged safely."""

    next_workers: Optional[List[str]]
    """Temp field for Dispatcher routing"""

    worker_tool_outputs: Annotated[Dict[str, List[Dict]], operator.or_]
    """Map of task_id -> List of {tool, args, output}. For Reviewer evidence."""

    # ========== Response Metadata ==========
    send_result: Optional[Dict]
    """Result of sending message via Meta API"""
