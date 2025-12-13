import asyncio
import logging
from app.services.meta_service import meta_service
from app.tools.instagram_tools import analyze_instagram_post
from app.tools.visual_tools import process_image_for_search
from app.utils.config import settings

logger = logging.getLogger(__name__)

class IngestionService:
    def __init__(self):
        # Local models removed. Relies entirely on MCP Knowledge Server.
        pass

    async def sync_instagram_products(self, limit: int = 10) -> str:
        """
        Sync products from Instagram to Knowledge Graph (Pinecone).
        """
        if not settings.INSTAGRAM_INGESTION_ENABLED:
             return "Instagram ingestion is disabled in settings."

        logger.info("🚀 Starting Instagram Inventory Sync (MCP Mode)...")
        
        try:
            # Lazy import MCP to avoid circular deps at startup if any
            from app.services.mcp_service import mcp_service
            
            posts = await meta_service.get_instagram_posts(limit=limit)
            if not posts:
                return "No posts found or failed to fetch from Instagram."
            
            logger.info(f"📥 Fetched {len(posts)} posts.")
            
            products_added = 0
            
            for post in posts:
                try:
                    post_id = post.get("id")
                    caption = post.get("caption", "")
                    media_type = post.get("media_type")
                    media_url = post.get("media_url")
                    permalink = post.get("permalink")
                    
                    if media_type == "VIDEO":
                        continue

                    # Analyze
                    analysis = await analyze_instagram_post(media_url, caption)
                    if not analysis or not analysis.get("is_product"):
                        continue
                        
                    p_name = analysis.get("name")
                    p_price = analysis.get("price", 0)
                    p_desc = analysis.get("description", "")
                    
                    # 1. Dupe Check via MCP (Text Search)
                    dupe_check = await mcp_service.call_tool("knowledge", "search_memory", {"query": p_name})
                    if dupe_check and "No matching products" not in dupe_check and p_name in dupe_check:
                         # Very loose duplicate check string matching, but efficient enough for agent
                         logger.info(f"Skipping likely duplicate: {p_name}")
                         continue

                    # 2. Upsert Text Product via MCP (Server handles embedding)
                    await mcp_service.call_tool("knowledge", "upsert_product", {
                        "name": p_name,
                        "description": p_desc,
                        "price": p_price,
                        "source": "instagram",
                        "image_url": media_url,
                        "permalink": permalink,
                        "item_id": post_id
                    })

                    # 3. Visual Embedding (Client-side DINOv2 -> MCP Store)
                    # We still do DINOv2 locally here via tool (since it uses HF API, not local model)
                    visual_embedding = await process_image_for_search.ainvoke(media_url)
                    
                    if visual_embedding:
                        vec_id = f"ig_{post_id}"
                        visual_metadata = {
                            "name": p_name,
                            "price": p_price,
                            "description": p_desc,
                            "source": "instagram",
                            "image_url": media_url,
                            "permalink": permalink,
                            "item_id": post_id
                        }
                        await mcp_service.call_tool("knowledge", "upsert_vector_data", {
                            "vector": visual_embedding,
                            "metadata": visual_metadata,
                            "id": vec_id
                        })
                    
                    products_added += 1
                    logger.info(f"Saved: {p_name}")
                    
                except Exception as inner_e:
                    logger.error(f"Error processing post {post.get('id')}: {inner_e}")
                    
            return f"Sync Complete. Added {products_added} new products."
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return f"Sync failed: {str(e)}"

# Singleton
ingestion_service = IngestionService()
