"""
Image Test Router: Test image search without WhatsApp/Instagram integration.
"""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import uuid
from pathlib import Path

router = APIRouter(prefix="/test/image", tags=["Image Testing"])
logger = logging.getLogger(__name__)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class ImageSearchResponse(BaseModel):
    status: str
    user_message: str
    ai_response: Optional[str]
    description: Optional[str]
    query_type: str
    messages_count: int
    error: Optional[str] = None


@router.post("/search", response_model=ImageSearchResponse)
async def test_image_search(
    file: UploadFile = File(..., description="Product image"),
    user_id: str = Form(default="test_user")
):
    """Upload image to search for matching products."""
    try:
        logger.info(f"Image search: {file.filename} from {user_id}")
        
        # Save uploaded file
        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = UPLOAD_DIR / unique_filename
        
        with open(file_path, "wb") as f:
            f.write(await file.read())
        
        from app.graphs.main_graph import app as graph_app
        from langchain_core.messages import HumanMessage
        
        human_msg = HumanMessage(content="Search for products")
        human_msg.additional_kwargs["image_url"] = str(file_path.absolute())
        
        input_state = {
            "messages": [human_msg],
            "user_id": user_id,
            "session_id": f"test_image_{user_id}",
            "platform": "test",
            "is_admin": False,
            "blocked": False,
            "order_intent": False,
            "requires_handoff": False,
            "query_type": "image"
        }
        
        result = await graph_app.ainvoke(input_state, config={"configurable": {"thread_id": f"img_{user_id}"}})
        
        messages = result.get("messages", [])
        ai_response = result.get("visual_matches", "")
        if not ai_response and len(messages) > 1:
            ai_response = messages[-1].content if hasattr(messages[-1], 'content') else str(messages[-1])
        
        return ImageSearchResponse(
            status="success", user_message=f"Image: {file.filename}", ai_response=ai_response,
            description=None, query_type="image", messages_count=len(messages)
        )
        
    except Exception as e:
        logger.error(f"Image search failed: {e}", exc_info=True)
        return ImageSearchResponse(
            status="error", user_message=f"Image: {file.filename}", ai_response=None,
            description=None, query_type="image", messages_count=0, error=str(e)
        )


@router.get("/info")
async def get_image_search_info():
    """Get image search capabilities info."""
    from app.utils.config import settings
    return {
        "status": "ok",
        "supported_formats": [".jpg", ".jpeg", ".png", ".webp"],
        "api_keys": {"llama_vision": bool(settings.LLAMA_API_KEY), "huggingface_dinov2": bool(settings.HUGGINGFACE_API_KEY)},
        "features": {"visual_similarity": "DINOv2", "semantic_search": "Llama Vision", "dual_strategy": "Combined"}
    }
