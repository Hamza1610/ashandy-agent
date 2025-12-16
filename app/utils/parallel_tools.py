"""
Parallel Tool Executor: Safely executes independent tools in parallel.

Key principle: Only tools without data dependencies can run in parallel.

Example:
  - search_products + check_stock → PARALLEL (independent)
  - search_products → format_results → SEQUENTIAL (dependent)
"""
import asyncio
import logging
from typing import List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ToolCall:
    """Represents a tool call with metadata."""
    name: str
    args: Dict[str, Any]
    executor: Callable[..., Awaitable[Any]]


# Tools that are always safe to parallelize (no shared state, no dependencies)
PARALLELIZABLE_TOOLS = {
    "search_products",
    "search_products_tool",
    "check_product_stock",
    "check_product_stock_tool",
    "search_text_products",
    "retrieve_user_memory",
    "calculate_delivery_fee",
    "calculate_delivery_fee_tool",
}

# Tools that should always run sequentially (write operations, stateful)
SEQUENTIAL_TOOLS = {
    "save_user_interaction",  # Writes to DB
    "approve_order",          # Modifies state
    "reject_order",           # Modifies state
    "generate_payment_link",  # Creates external resource
}


def can_parallelize(tool_names: List[str]) -> bool:
    """
    Check if a set of tools can be safely parallelized.
    
    Returns True only if ALL tools are in the parallelizable set
    and NONE are in the sequential set.
    """
    if not tool_names:
        return False
    
    # Check for sequential tools
    for name in tool_names:
        if name in SEQUENTIAL_TOOLS:
            logger.debug(f"Tool '{name}' requires sequential execution")
            return False
    
    # Check if all tools are explicitly parallelizable
    all_parallelizable = all(name in PARALLELIZABLE_TOOLS for name in tool_names)
    
    if not all_parallelizable:
        # Conservative: unknown tools run sequentially
        unknown = [n for n in tool_names if n not in PARALLELIZABLE_TOOLS]
        logger.debug(f"Unknown tools run sequentially: {unknown}")
        return False
    
    return True


async def execute_tools_smart(
    tool_calls: List[Dict[str, Any]],
    tool_executor: Callable[[str, Dict[str, Any]], Awaitable[str]]
) -> List[Dict[str, Any]]:
    """
    Smart tool executor: parallelizes safe tools, sequences others.
    
    Args:
        tool_calls: List of {"name": str, "args": dict}
        tool_executor: async function(name, args) -> output
    
    Returns:
        List of {"tool": name, "args": args, "output": output}
    """
    if not tool_calls:
        return []
    
    tool_names = [tc.get("name", tc.get("function", {}).get("name", "")) for tc in tool_calls]
    
    results = []
    
    if can_parallelize(tool_names):
        # PARALLEL: All tools are independent
        logger.info(f"Executing {len(tool_calls)} tools in PARALLEL: {tool_names}")
        
        async def execute_single(tc):
            name = tc.get("name", tc.get("function", {}).get("name", ""))
            args = tc.get("args", tc.get("function", {}).get("arguments", {}))
            try:
                output = await tool_executor(name, args)
                return {"tool": name, "args": args, "output": str(output)[:500]}
            except Exception as e:
                logger.error(f"Tool {name} failed: {e}")
                return {"tool": name, "args": args, "output": f"Error: {str(e)}"}
        
        # Run all tools concurrently
        results = await asyncio.gather(*[execute_single(tc) for tc in tool_calls])
        
    else:
        # SEQUENTIAL: At least one tool requires ordering
        logger.info(f"Executing {len(tool_calls)} tools SEQUENTIALLY: {tool_names}")
        
        for tc in tool_calls:
            name = tc.get("name", tc.get("function", {}).get("name", ""))
            args = tc.get("args", tc.get("function", {}).get("arguments", {}))
            try:
                output = await tool_executor(name, args)
                results.append({"tool": name, "args": args, "output": str(output)[:500]})
            except Exception as e:
                logger.error(f"Tool {name} failed: {e}")
                results.append({"tool": name, "args": args, "output": f"Error: {str(e)}"})
    
    return results
