"""
Order Extraction Tool: Extract structured order details from conversation.
"""
from langchain.tools import tool
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from app.services.llm_service import get_llm
from pydantic import BaseModel, Field
from typing import List
import logging

logger = logging.getLogger(__name__)


class OrderItem(BaseModel):
    name: str = Field(description="Product name")
    price: float = Field(description="Unit price")
    quantity: int = Field(description="Quantity")


class OrderData(BaseModel):
    items: List[OrderItem] = Field(description="Order items")
    subtotal: float = Field(description="Total before delivery")
    delivery_type: str = Field(description="pickup or delivery")
    delivery_details: dict = Field(description="name, phone, address, city")


@tool
async def extract_order_details(conversation_history: str) -> dict:
    """Extract structured order details from conversation."""
    try:
        llm = get_llm(model_type="versatile", temperature=0, json_mode=True)

        parser = JsonOutputParser(pydantic_object=OrderData)
        prompt = PromptTemplate(
            template="""Extract order from conversation:
{conversation}

Extract: Items (name, price, qty), Delivery type, Delivery details, Subtotal.
{format_instructions}
Return only JSON.""",
            input_variables=["conversation"],
            partial_variables={"format_instructions": parser.get_format_instructions()}
        )

        result = await (prompt | llm | parser).ainvoke({"conversation": conversation_history})
        return result

    except Exception as e:
        logger.error(f"Order extraction failed: {e}")
        return {"error": str(e)}
