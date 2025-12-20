"""
Helper utility to extract required tools from task descriptions.
This ensures consistent tool enforcement across all workers.
"""
import logging

logger = logging.getLogger(__name__)


def extract_required_tools_from_task(task_desc: str, worker_name: str = "worker") -> list[str]:
    """
    Extract required tools from task description using INTENT DETECTION.
    
    Uses fuzzy pattern matching to catch natural language task descriptions.
    Example: "Add product to cart" → detects add_to_cart intent
    
    Args:
        task_desc: Task description from planner
        worker_name: Name of worker for logging
        
    Returns:
        List of required tool names
    """
    required_tools = []
    task_lower = task_desc.lower()
    
    # Sales worker - Product tools
    # Search intent: "search", "find", "show", "look for" + product context
    if ("search" in task_lower or "find" in task_lower or "show" in task_lower or "look" in task_lower) and \
       ("product" in task_lower or "vitamin" in task_lower or "serum" in task_lower or "cream" in task_lower):
        required_tools.append("search_products")
    
    # Stock check intent: "check stock", "in stock", "available"
    if ("check" in task_lower or "verify" in task_lower) and ("stock" in task_lower or "available" in task_lower or "inventory" in task_lower):
        required_tools.append("check_product_stock")
    
    # Image detection intent: "detect", "analyze", "identify" + image context
    if ("detect" in task_lower or "analyze" in task_lower or "identify" in task_lower) and ("image" in task_lower or "photo" in task_lower or "picture" in task_lower):
        required_tools.append("detect_product_from_image")
    
    # Memory retrieval intent: "remember", "recall", "previous", "history"
    if "remember" in task_lower or "recall" in task_lower or "previous" in task_lower or "history" in task_lower or "memory" in task_lower:
        required_tools.append("retrieve_user_memory")
    
    # Sales worker - Cart tools (CRITICAL FOR CART SYSTEM)
    # Add to cart intent: "add" + ("cart" OR "order") OR "i'll take" OR "buy" OR "purchase"
    if (("add" in task_lower or "put" in task_lower or "include" in task_lower) and ("cart" in task_lower or "order" in task_lower)) or \
       "take" in task_lower or "buy" in task_lower or ("purchase" in task_lower and "add" not in task_lower):
        required_tools.append("add_to_cart")
    
    # View cart intent: "show cart", "view cart", "what's in cart", "cart summary"
    if ("show" in task_lower or "view" in task_lower or "see" in task_lower or "what" in task_lower or "display" in task_lower) and \
       ("cart" in task_lower or ("my" in task_lower and "order" in task_lower)):
        required_tools.append("get_cart_summary")
    
    # Remove from cart intent: "remove", "delete", "take out" + cart context
    if ("remove" in task_lower or "delete" in task_lower or ("take" in task_lower and "out" in task_lower)) and \
       ("cart" in task_lower or "order" in task_lower):
        required_tools.append("remove_from_cart")
    
    # Update quantity intent: "change", "update", "make it", "quantity" 
    if ("change" in task_lower or "update" in task_lower or ("make" in task_lower and ("it" in task_lower or "that" in task_lower))) and \
       ("quantity" in task_lower or "bottle" in task_lower or "unit" in task_lower or any(char.isdigit() for char in task_lower)):
        required_tools.append("update_cart_quantity")
    
    # Clear cart intent: "clear", "empty", "reset" + cart
    if ("clear" in task_lower or "empty" in task_lower or "reset" in task_lower) and "cart" in task_lower:
        required_tools.append("clear_cart")
    
    # Payment tools (payment_worker)
    if "use calculate_delivery_fee tool" in task_lower:
        required_tools.append("calculate_delivery_fee")
    if "use generate_payment_link tool" in task_lower:
        required_tools.append("generate_payment_link")
    if "use create_order_record tool" in task_lower:
        required_tools.append("create_order_record")
    if "use verify_payment tool" in task_lower:
        required_tools.append("verify_payment")
    if "use create_order_from_cart tool" in task_lower:
        required_tools.append("create_order_from_cart")
    if "use get_cart_total tool" in task_lower:
        required_tools.append("get_cart_total")
    if "use validate_order_ready tool" in task_lower:
        required_tools.append("validate_order_ready")
    if "use request_delivery_details tool" in task_lower:
        required_tools.append("request_delivery_details")
    if "use get_order_total_with_delivery tool" in task_lower:
        required_tools.append("get_order_total_with_delivery")
    if "use format_order_summary tool" in task_lower:
        required_tools.append("format_order_summary")
    if "use get_manual_payment_instructions tool" in task_lower:
        required_tools.append("get_manual_payment_instructions")
    if "use check_api_health tool" in task_lower:
        required_tools.append("check_api_health")
    
    # Admin tools (admin_worker)
    if "use generate_comprehensive_report tool" in task_lower:
        required_tools.append("generate_comprehensive_report")
    if "use list_pending_approvals tool" in task_lower:
        required_tools.append("list_pending_approvals")
    if "use approve_order tool" in task_lower:
        required_tools.append("approve_order")
    if "use reject_order tool" in task_lower:
        required_tools.append("reject_order")
    if "use get_pending_manual_payments tool" in task_lower:
        required_tools.append("get_pending_manual_payments")
    if "use confirm_manual_payment tool" in task_lower:
        required_tools.append("confirm_manual_payment")
    if "use reject_manual_payment tool" in task_lower:
        required_tools.append("reject_manual_payment")
    if "use get_recent_orders tool" in task_lower:
        required_tools.append("get_recent_orders")
    if "use search_order_by_customer tool" in task_lower:
        required_tools.append("search_order_by_customer")
    if "use view_order_details tool" in task_lower:
        required_tools.append("view_order_details")
    if "use relay_message_to_customer tool" in task_lower:
        required_tools.append("relay_message_to_customer")
    if "use notify_manager tool" in task_lower:
        required_tools.append("notify_manager")
    if "use get_incident_context tool" in task_lower:
        required_tools.append("get_incident_context")
    if "use resolve_incident tool" in task_lower:
        required_tools.append("resolve_incident")
    if "use report_incident tool" in task_lower:
        required_tools.append("report_incident")
    if "use get_top_customers tool" in task_lower:
        required_tools.append("get_top_customers")
    
    if required_tools:
        logger.info(f"⚠️ {worker_name.upper()} ENFORCING TOOLS: {required_tools}")
    
    return required_tools


def build_tool_enforcement_message(required_tools: list[str]) -> str:
    """
    Build enforcement message to append to system prompt.
    
    Args:
        required_tools: List of tool names that must be called
        
    Returns:
        Formatted enforcement message
    """
    if not required_tools:
        return ""
    
    return f"""

🚨 **CRITICAL: MANDATORY TOOL EXECUTION** 🚨
Your task REQUIRES you to call these tools IMMEDIATELY:
{', '.join([f'`{t}`' for t in required_tools])}

You MUST call these tools BEFORE doing anything else.
Failure to call these exact tools will result in task rejection.

**Example**: If task says "Use add_to_cart tool for CeraVe":
→ You MUST call: add_to_cart(product_name="CeraVe", quantity=1)
→ Do NOT skip this or substitute with text output
"""
