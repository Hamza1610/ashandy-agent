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
        from app.workflows.main_workflow import app as graph_app
        from langchain_core.messages import HumanMessage
        
        logger.info(f"Test: {request.message}")
        
        input_state = {
            "messages": [HumanMessage(content=request.message)],
            "user_id": request.user_id,
            "session_id": f"test_{request.user_id}",
            "platform": request.platform,
            "is_admin": request.is_admin,
            "blocked": False,
            "order_intent": False,
            "requires_handoff": False
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
        logger.error(f"Test failed: {e}", exc_info=True)
        return TestMessageResponse(
            status="error", user_message=request.message, ai_response=None,
            query_type=None, order_intent=None, messages_count=0, error=str(e)
        )


@router.get("/graph-info")
async def get_graph_info():
    """Get graph structure information."""
    try:
        from app.workflows.main_workflow import app as graph_app
        graph = graph_app.get_graph()
        nodes = list(graph.nodes.keys())
        return {"status": "ok", "graph_type": "LangGraph StateGraph", "node_count": len(nodes), "nodes": sorted(nodes)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
