import asyncio
import logging
from sentence_transformers import SentenceTransformer

from app.services.meta_service import meta_service
from app.services.vector_service import vector_service
from app.tools.instagram_tools import analyze_instagram_post
from app.tools.visual_tools import process_image_for_search
from app.utils.config import settings

logger = logging.getLogger(__name__)

# Initialize model once at module level (lazy load in function if needed for speed)
# but for a service, module level is fine if memory permits.
# To be safe for startup time, we load it inside the class or method.

class IngestionService:
    def __init__(self):
        self.text_model = None

    def get_model(self):
        if not self.text_model:
            self.text_model = SentenceTransformer('all-MiniLM-L6-v2')
        return self.text_model

    async def sync_instagram_products(self, limit: int = 10) -> str:
        """
        Sync products from Instagram to Pinecone.
        Returns a summary string of the operation.
        """
        if not settings.INSTAGRAM_INGESTION_ENABLED:
             return "Instagram ingestion is disabled in settings."

        logger.info("🚀 Starting Instagram Inventory Sync (Service)...")
        
        try:
            posts = await meta_service.get_instagram_posts(limit=limit)
            if not posts:
                return "No posts found or failed to fetch from Instagram."
            
            logger.info(f"📥 Fetched {len(posts)} posts.")
            
            model = self.get_model()
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
                    
                    # Dupe Check
                    name_vector = model.encode(p_name).tolist()
                    dupe_check = await vector_service.query_vectors(
                        index_name=settings.PINECONE_INDEX_PRODUCTS_TEXT,
                        vector=name_vector,
                        top_k=1,
                        filter_dict={"source": "phppos"}
                    )
                    
                    if dupe_check and dupe_check[0]['score'] > 0.85:
                        logger.info(f"Skipping duplicate: {p_name}")
                        continue
                        
                    # Visual Embedding
                    visual_embedding = await process_image_for_search.ainvoke(media_url)
                    if not visual_embedding:
                        continue
                        
                    # Upsert Visual
                    vec_id = f"ig_{post_id}"
                    visual_record = {
                        "id": vec_id,
                        "values": visual_embedding,
                        "metadata": {
                            "name": p_name,
                            "price": p_price,
                            "description": p_desc,
                            "source": "instagram",
                            "image_url": media_url,
                            "permalink": permalink,
                            "item_id": post_id
                        }
                    }
                    
                    # Upsert Text
                    text_context = f"{p_name}. {p_desc}"
                    text_embedding = model.encode(text_context).tolist()
                    text_record = {
                        "id": f"ig_txt_{post_id}",
                        "values": text_embedding,
                        "metadata": {
                            "name": p_name,
                            "price": p_price,
                            "description": p_desc,
                            "source": "instagram",
                            "text": text_context,
                            "image_url": media_url,
                            "permalink": permalink
                        }
                    }
                    
                    vector_service.upsert_vectors(settings.PINECONE_INDEX_PRODUCTS, [visual_record])
                    vector_service.upsert_vectors(settings.PINECONE_INDEX_PRODUCTS_TEXT, [text_record])
                    
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
