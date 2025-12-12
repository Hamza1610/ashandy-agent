"""
Test endpoints for image search functionality.
Allows manual image upload without needing WhatsApp/Instagram integration.
"""
from fastapi import APIRouter, File, UploadFile, Form, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import uuid
from pathlib import Path

router = APIRouter(prefix="/test/image", tags=["Image Testing"])
logger = logging.getLogger(__name__)

# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


class ImageSearchResponse(BaseModel):
    """Response schema for image search test."""
    status: str
    user_message: str
    ai_response: Optional[str]
    description: Optional[str]
    query_type: str
    messages_count: int
    error: Optional[str] = None


@router.post("/search", response_model=ImageSearchResponse)
async def test_image_search(
    file: UploadFile = File(..., description="Product image to search"),
    user_id: str = Form(default="test_user", description="User ID for testing")
):
    """
    Test image search without WhatsApp/Instagram.
    
    Upload a product image and get matching products from the database.
    
    **Flow**:
    1. Upload image → Saves locally
    2. Graph processes: Router → Visual Agent → Sales Agent
    3. Dual search: DINOv2 embeddings + Llama Vision description
    4. Returns product matches
    
    **Example**:
    ```bash
    curl -X POST http://localhost:8000/test/image/search \
      -F "file=@lipstick.jpg" \
      -F "user_id=test_123"
    ```
    """
    try:
        logger.info(f"Image search test: {file.filename} from {user_id}")
        
        # Save uploaded file
        file_ext = Path(file.filename).suffix
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = UPLOAD_DIR / unique_filename
        
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        logger.info(f"Image saved: {file_path}")
        
        # Create file URL (for local testing, use file:// URL)
        # In production, you'd upload to cloud storage and get public URL
        image_url = f"file://{file_path.absolute()}"
        
        # Import graph
        from app.graphs.main_graph import app as graph_app
        from langchain_core.messages import HumanMessage
        
        # Create state with image
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
            "query_type": "image"  # Force image type
        }
        
        logger.info("Invoking graph with image...")
        
        # Invoke graph
        result = await graph_app.ainvoke(
            input_state,
            config={"configurable": {"thread_id": f"img_{user_id}"}}
        )
        
        # Extract response
        messages = result.get("messages", [])
        ai_response = None
        description = None
        
        # Get visual matches if available
        visual_matches = result.get("visual_matches", "")
        if visual_matches:
            ai_response = visual_matches
        elif len(messages) > 1:
            last_msg = messages[-1]
            ai_response = last_msg.content if hasattr(last_msg, 'content') else str(last_msg)
        
        logger.info(f"Image search complete. Found {len(messages)} messages")
        
        return ImageSearchResponse(
            status="success",
            user_message=f"Image uploaded: {file.filename}",
            ai_response=ai_response,
            description=description,
            query_type="image",
            messages_count=len(messages)
        )
        
    except Exception as e:
        logger.error(f"Image search test failed: {e}", exc_info=True)
        return ImageSearchResponse(
            status="error",
            user_message=f"Image: {file.filename}",
            ai_response=None,
            description=None,
            query_type="image",
            messages_count=0,
            error=str(e)
        )


@router.get("/info")
async def get_image_search_info():
    """
    Get information about image search capabilities.
    
    Returns details about supported formats, API keys status, etc.
    """
    try:
        from app.utils.config import settings
        
        return {
            "status": "ok",
            "message": "Image search test endpoint ready",
            "supported_formats": [".jpg", ".jpeg", ".png", ".webp"],
            "api_keys": {
                "llama_vision": bool(settings.LLAMA_API_KEY),
                "huggingface_dinov2": bool(settings.HUGGINGFACE_API_KEY)  
            },
            "features": {
                "visual_similarity": "DINOv2 768-dim embeddings",
                "semantic_search": "Llama 3.2 Vision description",
                "dual_strategy": "Combines both for best results"
            },
            "upload_dir": str(UPLOAD_DIR.absolute())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
