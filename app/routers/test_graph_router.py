"""
Test Graph Router: API endpoint to test LangGraph workflow without WhatsApp/Instagram.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging

router = APIRouter(prefix="/test", tags=["Testing"])
logger = logging.getLogger(__name__)


class TestMessageRequest(BaseModel):
    message: str
    user_id: str = "test_user"
    platform: str = "whatsapp"
    is_admin: bool = False


class TestMessageResponse(BaseModel):
    status: str
    user_message: str
    ai_response: Optional[str]
    query_type: Optional[str]
    order_intent: Optional[bool]
    messages_count: int
    error: Optional[str] = None


@router.post("/message", response_model=TestMessageResponse)
async def test_graph_message(request: TestMessageRequest):
    """Test graph workflow. POST {"message": "Do you have lipstick?", "user_id": "test_123"}"""
    try:
        from app.graphs.main_graph import app as graph_app
        from langchain_core.messages import HumanMessage, AIMessage
        from app.services.db_service import AsyncSessionLocal
        from sqlalchemy import text
        
        # DEBUG: Check what checkpointer we really have
        try:
            cp = graph_app.checkpointer
            logger.info(f"DEBUG: Checkpointer type: {type(cp).__name__}")
            if hasattr(cp, 'get_next_version'):
                logger.info("DEBUG: Checkpointer has get_next_version")
            else:
                logger.error("DEBUG: Checkpointer MISSING get_next_version (it is likely a context manager wrapper)")
        except Exception as deb_e:
            logger.error(f"DEBUG: Failed to inspect checkpointer: {deb_e}")

        logger.info(f"Test: {request.message}")
        
        # Load conversation history from database
        messages = []
        try:
            async with AsyncSessionLocal() as session:
                query = text("""
                    SELECT role, content FROM message_logs 
                    WHERE user_id = :user_id 
                    ORDER BY created_at DESC LIMIT 10
                """)
                result = await session.execute(query, {"user_id": request.user_id})
                rows = result.fetchall()
                
                # Reverse to get chronological order (oldest first)
                for row in reversed(rows):
                    role, content = row
                    if role == "user":
                        messages.append(HumanMessage(content=content))
                    elif role == "assistant":
                        messages.append(AIMessage(content=content))
        except Exception as e:
            logger.warning(f"Could not load history: {e}")
        
        # Add current message
        messages.append(HumanMessage(content=request.message))
        
        # Try to get previous state from checkpointer to preserve order_intent
        previous_order_intent = False
        previous_order = None
        previous_order_data = None
        try:
            from app.graphs.main_graph import app as graph_check
            config = {"configurable": {"thread_id": request.user_id}}
            # Use aget_state for AsyncRedisSaver compatibility
            state_snapshot = await graph_check.aget_state(config)
            if state_snapshot and state_snapshot.values:
                previous_order_intent = state_snapshot.values.get("order_intent", False)
                previous_order = state_snapshot.values.get("order")
                previous_order_data = state_snapshot.values.get("order_data")
                logger.info(f"Loaded previous state: order_intent={previous_order_intent}, order={previous_order}")
        except Exception as e:
            logger.debug(f"No previous state (or error loading it): {e}")
        
        input_state = {
            "messages": messages,
            "user_id": request.user_id,
            "session_id": f"test_{request.user_id}",
            "platform": "test",
            "is_admin": request.is_admin,
            "blocked": False,
            "order_intent": previous_order_intent,  # Preserve from previous state!
            "order": previous_order,  # Preserve order data
            "order_data": previous_order_data,  # Preserve order_data for delivery details
            "requires_handoff": False,
            # Initialize empty structures to prevent KeyError in new nodes
            "task_statuses": {},
            "worker_outputs": {},
            "retry_counts": {}
        }
        
        result = await graph_app.ainvoke(input_state, config={"configurable": {"thread_id": request.user_id}})
        
        messages = result.get("messages", [])
        ai_response = None
        
        for msg in reversed(messages):
            if hasattr(msg, "type") and msg.type == "ai":
                ai_response = msg.content
                break
            if msg.__class__.__name__ == "AIMessage":
                ai_response = msg.content
                break
        
        if not ai_response:
            ai_response = result.get("worker_result")
        
        return TestMessageResponse(
            status="success",
            user_message=request.message,
            ai_response=ai_response,
            query_type=result.get("query_type"),
            order_intent=result.get("order_intent"),
            messages_count=len(messages)
        )
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(f"Test failed: {e}\n{tb}")
        return TestMessageResponse(
            status="error",
            user_message=request.message,
            ai_response=None,
            query_type=None,
            order_intent=None,
            messages_count=0,
            error=f"{str(e)}\n\nTraceback:\n{tb}"
        )


@router.get("/graph-info")
async def get_graph_info():
    """Get graph structure information."""
    try:
        from app.graphs.main_graph import app as graph_app
        graph = graph_app.get_graph()
        nodes = list(graph.nodes.keys())
        return {"status": "ok", "graph_type": "LangGraph StateGraph", "node_count": len(nodes), "nodes": sorted(nodes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
