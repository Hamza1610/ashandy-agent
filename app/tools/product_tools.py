"""
Product search tools for the Awelewa agent system.
All tools follow the LangChain @tool pattern for LLM binding.
"""
from langchain.tools import tool
from app.tools.db_tools import get_product_details
from app.tools.pos_connector_tools import search_phppos_products
import logging

logger = logging.getLogger(__name__)


@tool("search_products_tool")
async def search_products(query: str) -> str:
    """
    Search for products using text query (searches both POS inventory and Instagram catalog).
    
    Args:
        query: Customer's product search query (e.g., "red lipstick", "dry skin cream")
        
    Returns:
        Formatted string with product matches including names, prices, and source.
    """
    try:
        print(f"\n>>> TOOL: search_products called with query='{query}'")
        logger.info(f"Product search tool called with query: '{query}'")
        
        # 1. Generate Query Vector
        # We need to initialize the model inside the tool or globally.
        # Ideally globally, but for now importing here ensures no circular deps during startup if not careful.
        from sentence_transformers import SentenceTransformer
        from app.services.vector_service import vector_service
        from app.utils.config import settings
        
        # This might be slow if loaded every time. In prod, load once in app startup.
        # Checking if model is already loaded in app state would be better, but for simplicity:
        model = SentenceTransformer('all-MiniLM-L6-v2') 
        query_vector = model.encode(query).tolist()
        
        # 2. Query Pinecone
        matches = await vector_service.query_vectors(
            index_name=settings.PINECONE_INDEX_PRODUCTS_TEXT,
            vector=query_vector,
            top_k=5
        )
        
        if not matches:
             # Fallback to direct POS search if vector search fails or returns nothing?
             logger.info("Vector search returned no results. Trying legacy POS search fallback.")
             # Use existing POS connector tool
             results = await search_phppos_products.ainvoke(query)
             return f"Direct POS Search Results:\n{results}"

        # 3. Format Results
        result_str = "Found the following products:\n"
        for i, m in enumerate(matches):
            meta = m.get("metadata", {})
            name = meta.get("name", "Unknown")
            price = meta.get("price", "N/A")
            desc = meta.get("description", "")[:100] + "..."
            source = meta.get("source", "unknown").upper()
            
            # Format price nicely
            try:
                price_float = float(price)
                price_display = f"₦{price_float:,.2f}"
            except:
                price_display = str(price)
            
            result_str += f"""
{i+1}. **{name}**
   - Price: {price_display}
   - Source: {source}
   - Details: {desc}
"""
        return result_str
        
    except Exception as e:
        print(f"\n>>> TOOL ERROR in search_products: {type(e).__name__}: {str(e)}")
        logger.error(f"Product search failed: {e}", exc_info=True)
        return f"I encountered an error searching for products. Please try again."


@tool("get_product_by_id_tool")
async def get_product_by_id(product_id: str) -> str:
    """
    Get detailed information about a specific product by ID.
    
    Args:
        product_id: The product identifier
        
    Returns:
        Detailed product information including price, stock, description
    """
    try:
        logger.info(f"Getting product details for ID: {product_id}")
        
        result = await get_product_details.ainvoke(product_id)
        
        if not result:
            return f"Product with ID '{product_id}' not found."
        
        return f"Product Details:\n{result}"
        
    except Exception as e:
        logger.error(f"Product detail fetch failed: {e}")
        return f"Could not retrieve product details. Please try again."


@tool("check_product_stock_tool")
async def check_product_stock(product_name: str) -> str:
    """
    Check if a specific product is in stock.
    
    Args:
        product_name: Name of the product to check
        
    Returns:
        Stock availability status
    """
    try:
        logger.info(f"Checking stock for: {product_name}")
        
        # Search for the product first
        search_result = await search_phppos_products.ainvoke(product_name)
        
        if "No products found" in search_result:
            return f"'{product_name}' is not available in our inventory."
        
        # Extract stock info from search results
        # The search results should include stock status
        return search_result
        
    except Exception as e:
        logger.error(f"Stock check failed: {e}")
        return "Could not check stock availability. Please contact support."
