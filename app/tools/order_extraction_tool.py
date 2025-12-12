from langchain.tools import tool
from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.utils.config import settings
from pydantic import BaseModel, Field
from typing import List
import logging

logger = logging.getLogger(__name__)

class OrderItem(BaseModel):
    name: str = Field(description="Name of the product")
    price: float = Field(description="Price per unit")
    quantity: int = Field(description="Quantity ordered")

class OrderData(BaseModel):
    items: List[OrderItem] = Field(description="List of items in the order")
    subtotal: float = Field(description="Total price of items before delivery")
    delivery_type: str = Field(description="pickup or delivery")
    delivery_details: dict = Field(description="name, phone, address, city, state")

@tool
async def extract_order_details(conversation_history: str) -> dict:
    """
    Extracts structured order details (items, price, delivery info) from the conversation history.
    Use this when the user has confirmed their order.
    """
    if not settings.LLAMA_API_KEY:
        return {"error": "LLM API Key missing"}

    try:
        llm = ChatGroq(
            temperature=0,
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="meta-llama/llama-3.3-70b-versatile", # Using a smarter model for extraction
            model_kwargs={"response_format": {"type": "json_object"}}
        )

        parser = JsonOutputParser(pydantic_object=OrderData)

        prompt = PromptTemplate(
            template="""You are an Order Extraction API. Extract the final confirmed order details from the conversation below.
            
            Conversation:
            {conversation}
            
            Extract:
            1. List of items (Name, Price, Quantity).
            2. Delivery Type (pickup or delivery).
            3. Delivery Details (Name, Phone, Address, City, State) if provided.
            4. Subtotal (Sum of Item Price * Quantity).

            {format_instructions}
            
            Return ONLY JSON. If info is missing, use null or empty string.
            """,
            input_variables=["conversation"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )

        chain = prompt | llm | parser
        
        result = await chain.ainvoke({"conversation": conversation_history})
        return result

    except Exception as e:
        logger.error(f"Order extraction failed: {e}")
        return {"error": str(e)}
