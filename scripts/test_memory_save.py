import asyncio
import logging
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Mock settings just in case, but we prefer loading from env
try:
    from app.utils.config import settings
    print(f"Index Name: {settings.PINECONE_INDEX_USER_MEMORY}")
except ImportError:
    print("Could not import config.")

async def test_memory():
    print("--- Testing Memory Save ---")
    try:
        from app.tools.vector_tools import save_user_interaction, embedding_model
        
        if embedding_model is None:
            print("ERROR: Embedding model failed to load! This is the root cause.")
            return

        result = await save_user_interaction.ainvoke({
            "user_id": "test_user_DEBUG",
            "user_msg": "Hello Debug",
            "ai_msg": "Hello User"
        })
        print(f"Result: {result}")
        
    except Exception as e:
        print(f"CRASH: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_memory())
