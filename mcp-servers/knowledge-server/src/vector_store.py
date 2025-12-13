import os
import logging
import time
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("knowledge-store")

class VectorStore:
    def __init__(self):
        self.api_key = os.getenv("PINECONE_API_KEY")
        self.env = os.getenv("PINECONE_ENVIRONMENT", "us-east-1")
        self.index_name_products = os.getenv("PINECONE_INDEX_PRODUCTS_TEXT", "ashandy-products-text")
        self.index_name_visual = os.getenv("PINECONE_INDEX_PRODUCTS", "ashandy-products")
        self.index_name_memory = os.getenv("PINECONE_INDEX_USER_MEMORY", "ashandy-user-memory")
        
        self.pc = None
        self.model = None

        # Initialize Pinecone
        if self.api_key:
            try:
                self.pc = Pinecone(api_key=self.api_key)
                self._ensure_index_exists(self.index_name_products, dimension=384)
                self._ensure_index_exists(self.index_name_visual, dimension=768)
                self._ensure_index_exists(self.index_name_memory, dimension=384)
            except Exception as e:
                logger.error(f"Pinecone Init Failed: {e}")
        else:
            logger.error("PINECONE_API_KEY missing.")

        # Initialize Model (Lazy load or instant?)
        # Instant load is better for server readiness
        try:
            logger.info("Loading SentenceTransformer model...")
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Model loaded.")
        except Exception as e:
            logger.error(f"Model Load Failed: {e}")

    def _ensure_index_exists(self, index_name: str, dimension: int):
        if not self.pc: return
        try:
            existing = [i.name for i in self.pc.list_indexes()]
            if index_name not in existing:
                logger.info(f"Creating index: {index_name}")
                self.pc.create_index(
                    name=index_name,
                    dimension=dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region="us-east-1")
                )
                while not self.pc.describe_index(index_name).status['ready']:
                    time.sleep(1)
        except Exception as e:
            logger.warning(f"Index creation check failed (likely auth or quota): {e}")

    def search(self, query: str, top_k: int = 5) -> str:
        """
        Embed query -> Search Pinecone -> Return formatted string.
        """
        if not self.pc or not self.model:
            return "Error: vector services unavailable."

        try:
            vector = self.model.encode(query).tolist()
            index = self.pc.Index(self.index_name_products)
            
            response = index.query(
                vector=vector,
                top_k=top_k,
                include_metadata=True
            )
            
            matches = response.get("matches", [])
            if not matches:
                return "No matching products found."
            
            # Format results similar to original to keep Agent happy
            result_str = "Found relevant products:\n"
            for m in matches:
                meta = m.get("metadata", {})
                name = meta.get("name", "Unknown")
                price = meta.get("price", "N/A")
                source = meta.get("source", "unknown")
                result_str += f"- {name} (Price: {price}, Source: {source})\n"
                
            return result_str

        except Exception as e:
            logger.error(f"Search Error: {e}")
            return f"Search failed: {str(e)}"

    def upsert_text(self, text: str, metadata: dict, id: str = None) -> str:
        """
        Embed text -> Upsert to Pinecone.
        """
        if not self.pc or not self.model:
            return "Error: Services unavailable."
            
        try:
            vector = self.model.encode(text).tolist()
            if not id:
                id = str(time.time()) # Simple ID
            
            index = self.pc.Index(self.index_name_products)
            index.upsert(vectors=[
                (id, vector, metadata)
            ])
            return "Successfully stored memory."
        except Exception as e:
            return f"Upsert failed: {str(e)}"

    def upsert_vector(self, vector: list, metadata: dict, id: str) -> str:
        """
        Upsert a pre-calculated vector (e.g. Visual Embedding).
        """
        if not self.pc:
            return "Error: Pinecone unavailable."
            
        try:
            # Determine index based on dimension (Visual=768)
            dim = len(vector)
            index_name = self.index_name_visual if dim == 768 else self.index_name_products
            
            index = self.pc.Index(index_name)
            index.upsert(vectors=[
                (id, vector, metadata)
            ])
            return "Successfully stored vector."
        except Exception as e:
            return f"Upsert Vector failed: {str(e)}"

    def search_by_vector(self, vector: list, top_k: int = 5) -> str:
        """
        Search Pinecone using a direct vector (e.g. Visual Embedding).
        """
        if not self.pc:
            return "Error: Pinecone unavailable."
            
        try:
            dim = len(vector)
            index_name = self.index_name_visual if dim == 768 else self.index_name_products
            
            index = self.pc.Index(index_name)
            response = index.query(
                vector=vector,
                top_k=top_k,
                include_metadata=True
            )
            
            matches = response.get("matches", [])
            if not matches:
                return "No matching products found."
            
            result_str = "Found relevant products:\n"
            for m in matches:
                meta = m.get("metadata", {})
                name = meta.get("name", "Unknown")
                price = meta.get("price", "N/A")
                source = meta.get("source", "unknown")
                result_str += f"- {name} (Price: {price}, Source: {source})\n"
                
            return result_str
            
        except Exception as e:
            return f"Search Vector failed: {str(e)}"

    def search_memory_for_user(self, query: str, user_id: str, top_k: int = 3) -> str:
        """
        Search user-specific memory.
        """
        if not self.pc or not self.model:
            return "Error: Services unavailable."
            
        try:
            vector = self.model.encode(query).tolist()
            index = self.pc.Index(self.index_name_memory)
            
            response = index.query(
                vector=vector,
                top_k=top_k,
                include_metadata=True,
                filter={"user_id": user_id}
            )
            
            matches = response.get("matches", [])
            if not matches:
                return "No previous memory found."
            
            memory_text = "\n".join([m['metadata'].get('memory_text', '') for m in matches])
            return f"User Context:\n{memory_text}"
            
        except Exception as e:
            return f"Memory Search Failed: {str(e)}"

    def save_interaction(self, user_id: str, text: str, meta: dict = None) -> str:
        """
        Save interaction to user memory.
        """
        if not self.pc or not self.model:
            return "Error: Services unavailable."
            
        try:
            vector = self.model.encode(text).tolist()
            timestamp = time.time()
            vector_id = f"{user_id}_{int(timestamp)}"
            
            metadata = meta or {}
            metadata.update({
                "user_id": user_id,
                "memory_text": text,
                "timestamp": timestamp,
                "type": "interaction"
            })
            
            index = self.pc.Index(self.index_name_memory)
            index.upsert(vectors=[
                (vector_id, vector, metadata)
            ])
            return f"Interaction saved (ID: {vector_id})."
        except Exception as e:
            return f"Save Interaction Failed: {str(e)}"
