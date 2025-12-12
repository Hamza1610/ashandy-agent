import asyncio
import sys
import os

# Add the project root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import requests
from app.services.vector_service import vector_service
from app.utils.config import settings
from huggingface_hub import InferenceClient
from PIL import Image
import io
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def validate_config():
    """Ensure all required settings are present."""
    missing = []
    if not settings.POS_CONNECTOR_API_KEY: missing.append("POS_CONNECTOR_API_KEY")
    if not settings.HUGGINGFACE_API_KEY: missing.append("HUGGINGFACE_API_KEY")
    if not settings.PINECONE_API_KEY: missing.append("PINECONE_API_KEY")
    
    if missing:
        logger.error(f"Missing configuration variables: {', '.join(missing)}")
        logger.error("Please check your .env file. Note: python-dotenv reported parsing errors.")
        return False
    return True

def fetch_phppos_items():
    """Fetch all items from PHPPOS API (Synchronous)."""
    url = f"{settings.PHPPOS_BASE_URL}/items"
    headers = {
        "accept": "application/json",
        "x-api-key": settings.POS_CONNECTOR_API_KEY,
        "User-Agent": "curl/8.5.0"
    }
    
    try:
        logger.info(f"Fetching products from {url}...")
        response = requests.get(url, headers=headers, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Fetched {len(data)} items from PHPPOS.")
        return data
    except Exception as e:
        logger.error(f"Failed to fetch from PHPPOS: {e}")
        return []

def get_image_embedding(image_url: str):
    """
    Generate 768-dim embedding using DINOv2 via HF InferenceClient.
    Note: We need a valid HF token.
    """
    if not settings.HUGGINGFACE_API_KEY:
        logger.error("HUGGINGFACE_API_KEY is missing.")
        return None

    try:
        # We can pass the URL directly to the API in some cases, 
        # or download and send bytes. Reliability is higher with bytes.
        # But for DINOv2 feature-extraction, the API supports image input.
        
        # NOTE: Using 'facebook/dinov2-base' for embedding
        client = InferenceClient(token=settings.HUGGINGFACE_API_KEY)
        
        # Feature extraction usually returns a list of floats
        # We might need to handle image download if the API expects bytes
        # Let's try passing the URL to the API feature extraction if supported,
        # otherwise we download.
        
        output = client.feature_extraction(
            image_url, 
            model="facebook/dinov2-base"
        )
        return output
        
    except Exception as e:
        logger.error(f"Embedding generation failed for {image_url}: {e}")
        return None

async def ingest_products():
    """Main ingestion flow."""
    if not validate_config():
        return

    # 0. Load Text Model
    from sentence_transformers import SentenceTransformer
    text_model = SentenceTransformer('all-MiniLM-L6-v2') # 384 dim

    # 1. Fetch Items
    items = fetch_phppos_items()
    if not items:
        return

    vectors_to_upsert = []
    text_vectors_to_upsert = []
    
    # 2. Process Items
    for item in items:
        item_id = str(item.get("item_id"))
        name = item.get("name")
        price = item.get("unit_price") 
        description = item.get("description") or ""
        images = item.get("images", [])
        
        if not name:
            continue
            
        logger.info(f"Processing {name} ({item_id})...")

        # --- TEXT EMBEDDING ---
        # Combine name and description
        text_content = f"{name}. {description}"
        text_embed = text_model.encode(text_content).tolist()
        
        text_vector = {
            "id": f"phppos_txt_{item_id}",
            "values": text_embed,
            "metadata": {
                "name": name,
                "price": price,
                "item_id": item_id,
                "source": "phppos",
                "text": text_content
            }
        }
        text_vectors_to_upsert.append(text_vector)

        # --- VISUAL EMBEDDING ---
        # Skip if no image
        image_url = None
        if len(images) > 0:
             img_entry = images[0]
             if isinstance(img_entry, str):
                 image_url = img_entry
             elif isinstance(img_entry, dict):
                 image_url = img_entry.get("url") or img_entry.get("public_url")
        
        if image_url:
            embedding = await asyncio.to_thread(get_image_embedding, image_url)
            
            if embedding:
                vector = {
                    "id": f"phppos_{item_id}",
                    "values": embedding,
                    "metadata": {
                        "name": name,
                        "price": price,
                        "item_id": item_id,
                        "source": "phppos",
                        "image_url": image_url
                    }
                }
                vectors_to_upsert.append(vector)
            
        # Batch upsert
        if len(vectors_to_upsert) >= 20:
            vector_service.upsert_vectors(settings.PINECONE_INDEX_PRODUCTS, vectors_to_upsert)
            vectors_to_upsert = []
            
        if len(text_vectors_to_upsert) >= 50:
             vector_service.upsert_vectors(settings.PINECONE_INDEX_PRODUCTS_TEXT, text_vectors_to_upsert)
             text_vectors_to_upsert = []

    # Final batch
    if vectors_to_upsert:
        vector_service.upsert_vectors(settings.PINECONE_INDEX_PRODUCTS, vectors_to_upsert)
    if text_vectors_to_upsert:
        vector_service.upsert_vectors(settings.PINECONE_INDEX_PRODUCTS_TEXT, text_vectors_to_upsert)

if __name__ == "__main__":
    asyncio.run(ingest_products())
