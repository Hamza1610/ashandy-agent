from app.models.agent_states import AgentState
from app.tools.db_tools import check_admin_whitelist
from langchain_core.messages import HumanMessage
import logging
import json

logger = logging.getLogger(__name__)

async def router_agent_node(state: AgentState):
    """
    Router Agent: Classifies user and query type with robust logic.
    """
    try:
        messages = state.get("messages", [])
        if not messages:
            return {"error": "No messages to route."}
            
        last_message = messages[-1]
        sender_id = state.get("user_id", "unknown")
        
        # 1. Check Admin Whitelist
        is_admin = False
        try:
            is_admin = await check_admin_whitelist.ainvoke(sender_id)
        except Exception as e:
            logger.error(f"Whitelist check failed: {e}")
            
        # 2. Determine Query Type (Text vs Image vs Command)
        query_type = "text" # default
        image_url = None
        
        if isinstance(last_message, HumanMessage):
             # Check for image content in message
             # Handle standard LangChain multimodal content type (list of dicts)
             if isinstance(last_message.content, list):
                 for content_part in last_message.content:
                     if isinstance(content_part, dict) and content_part.get("type") == "image_url":
                         image_url = content_part["image_url"].get("url")
                         query_type = "image"
                         break
             
             # Also check additional_kwargs as fallback (webhook might populate this)
             if not image_url and last_message.additional_kwargs.get("image_url"):
                 image_url = last_message.additional_kwargs["image_url"]
                 query_type = "image"

        # Admin commands check (Overrules standard text/image if admin)
        content_text = ""
        if isinstance(last_message.content, str):
            content_text = last_message.content
        elif isinstance(last_message.content, list):
            # Extract text part
            for part in last_message.content:
                 if part.get("type") == "text":
                     content_text = part.get("text", "")

        if is_admin and content_text.strip().startswith("/"):
            query_type = "admin_command"
            state["admin_command"] = content_text.strip()

        return {
            "is_admin": is_admin,
            "query_type": query_type,
            "image_url": image_url
        }

    except Exception as e:
        logger.error(f"Router Agent Error: {e}")
        return {"error": str(e)}

