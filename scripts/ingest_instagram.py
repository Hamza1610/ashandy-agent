import asyncio
import sys
import os
import logging

# Add the project root directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.ingestion_service import ingestion_service

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IG_INGEST")

async def ingest_instagram_products():
    """
    Main flow to ingest Instagram products into Pinecone inventory via Service.
    """
    logger.info("Starting Script Wrapper for Ingestion...")
    result = await ingestion_service.sync_instagram_products(limit=20)
    logger.info(result)

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(ingest_instagram_products())
