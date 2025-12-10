from pinecone import Pinecone, ServerlessSpec, PodSpec
from app.utils.config import settings
import logging
import time

logger = logging.getLogger(__name__)

class VectorService:
    def __init__(self):
        self.api_key = settings.PINECONE_API_KEY
        self.env = settings.PINECONE_ENVIRONMENT
        self.index_user_memory = settings.PINECONE_INDEX_USER_MEMORY
        self.index_products = settings.PINECONE_INDEX_PRODUCTS
        self.pc = None

        if self.api_key:
            try:
                self.pc = Pinecone(api_key=self.api_key)
                self._ensure_index_exists(self.index_user_memory, dimension=384) # 384 for text
                self._ensure_index_exists(self.index_products, dimension=768)   # 768 for vision
                if hasattr(settings, "PINECONE_INDEX_PRODUCTS_TEXT"):
                    self._ensure_index_exists(settings.PINECONE_INDEX_PRODUCTS_TEXT, dimension=384)
            except Exception as e:
                 logger.error(f"Failed to initialize Pinecone: {e}", exc_info=True)
        else:
            logger.error("PINECONE_API_KEY not set. Vector service functionality will fail.")

    def _ensure_index_exists(self, index_name: str, dimension: int):
        """Check if index exists, create if not."""
        if not self.pc: 
            return

        try:
            existing_indexes = [i.name for i in self.pc.list_indexes()]
            if index_name not in existing_indexes:
                logger.info(f"Creating Pinecone index: {index_name}")
                # Use ServerlessSpec for AWS starter or PodSpec for others. 
                # Defaulting to Serverless for new Pinecone users on AWS.
                self.pc.create_index(
                    name=index_name,
                    dimension=dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1") # Adjust region as needed
                )
                # Wait for index to be ready
                while not self.pc.describe_index(index_name).status['ready']:
                    time.sleep(1)
                logger.info(f"Index {index_name} is ready.")
        except Exception as e:
            if "403" in str(e) and "max serverless indexes" in str(e):
                logger.warning(f"Quota exceeded creating {index_name}. Assuming it exists or user will manage it.")
            else:
                logger.error(f"Error checking/creating index {index_name}: {e}")

    def upsert_vectors(self, index_name: str, vectors: list):
        if not self.pc:
            logger.error("Pinecone client not initialized.")
            return

        try:
             index = self.pc.Index(index_name)
             index.upsert(vectors=vectors)
             logger.info(f"Successfully upserted {len(vectors)} vectors to {index_name}")
        except Exception as e:
            logger.error(f"Pinecone upsert error in {index_name}: {e}")
            raise e

    def query_vectors(self, index_name: str, vector: list, top_k: int = 5, filter_metadata: dict = None):
        if not self.pc:
            logger.error("Pinecone client not initialized.")
            return {"matches": []}

        try:
            index = self.pc.Index(index_name)
            response = index.query(
                vector=vector,
                top_k=top_k,
                include_metadata=True,
                filter=filter_metadata
            )
            return response
        except Exception as e:
            logger.error(f"Pinecone query error in {index_name}: {e}")
            raise e

vector_service = VectorService()
