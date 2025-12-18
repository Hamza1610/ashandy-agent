"""
Tool Knowledge Registry for Reviewer Agent.

This module provides comprehensive tool definitions that enable the reviewer
to validate worker outputs accurately and provide contextual recommendations.
"""
from typing import Dict, List, Any


# =============================================================================
# TOOL KNOWLEDGE REGISTRY
# =============================================================================

TOOL_KNOWLEDGE: Dict[str, Dict[str, Any]] = {
    # =========================================================================
    # SALES WORKER TOOLS
    # =========================================================================
    "search_products": {
        "worker": "sales_worker",
        "purpose": "Search product catalog by name, category, or keywords",
        "expected_output": "Product list with Name, Price (₦), Description",
        "success_indicators": ["Name:", "Price", "₦", "product"],
        "failure_modes": {
            "No results found": "Suggest broader keywords (e.g., 'lotion' instead of 'CeraVe PM Lotion')",
            "Connection error": "MCP POS service may be down - retry or escalate",
            "Empty response": "Check query spelling or try alternative product names"
        },
        "validation_rules": [
            "Product names should reasonably match tool output (fuzzy matching allowed)",
            "Prices must match numerically (allow formatting like 18k = 18000 = 18,000)",
            "Worker MAY suggest adjacent relevant products found in the database results"
        ]
    },
    
    "check_product_stock": {
        "worker": "sales_worker",
        "purpose": "Verify product availability (existence = available)",
        "expected_output": "Availability status, product info if found",
        "success_indicators": ["available", "found", "in stock", "Name:"],
        "failure_modes": {
            "Not found": "Search using alternative name or recommend similar products",
            "Error": "Retry with exact product name from search_products results"
        },
        "validation_rules": [
            "If product exists in database, consider it available",
            "Do NOT mention stock counts (POS data unreliable)"
        ]
    },
    
    "detect_product_from_image": {
        "worker": "sales_worker",
        "purpose": "Analyze customer image to extract product text, type, and visual features",
        "expected_output": "Dict with detected_text, product_type, visual_description, matched_products",
        "success_indicators": ["detected_text", "product_type", "visual_description"],
        "failure_modes": {
            "Could not analyze": "Image quality may be poor - ask customer for clearer photo",
            "No text detected": "Use visual_description to search instead of text",
            "Search failed": "Manually describe what was seen and search by description"
        },
        "validation_rules": [
            "Visual search results are valid evidence for product recommendations",
            "matched_products from visual analysis are acceptable product sources"
        ]
    },
    
    "retrieve_user_memory": {
        "worker": "sales_worker",
        "purpose": "Retrieve customer profile, preferences, and purchase history",
        "expected_output": "Customer context including past purchases, preferences",
        "success_indicators": ["user", "purchase", "preference", "history"],
        "failure_modes": {
            "No memory found": "New customer - proceed without personalization",
            "Error retrieving": "Knowledge MCP may be down - safe to continue without memory"
        },
        "validation_rules": [
            "Memory retrieval is optional - failure should not block response",
            "Past purchases can inform recommendations but are not required evidence"
        ]
    },
    
    "save_user_interaction": {
        "worker": "sales_worker",
        "purpose": "Save chat interaction to long-term memory",
        "expected_output": "Confirmation of save",
        "success_indicators": ["saved", "success", "stored"],
        "failure_modes": {
            "Failed to save": "Non-critical - log but continue"
        },
        "validation_rules": [
            "This is a background operation - does not affect customer response",
            "Failure to save should not cause rejection"
        ]
    },
    
    "search_text_products": {
        "worker": "sales_worker",
        "purpose": "Semantic text search for products in vector database",
        "expected_output": "Product matches from semantic search",
        "success_indicators": ["product", "match", "found", "similar"],
        "failure_modes": {
            "No matches": "Try broader search terms or use search_products instead",
            "Vector DB error": "Fall back to POS search_products"
        },
        "validation_rules": [
            "Semantic search results are valid product evidence",
            "Can complement or replace exact search_products"
        ]
    },
    
    "process_image_for_search": {
        "worker": "sales_worker",
        "purpose": "Generate visual embedding from product image for similarity search",
        "expected_output": "768-dimension vector embedding for visual search",
        "success_indicators": ["embedding", "vector", "dimensions"],
        "failure_modes": {
            "Image download failed": "Ask customer to resend the image",
            "API timeout": "DINOv2 service may be slow - retry",
            "Invalid image": "Image format not supported - ask for JPEG/PNG"
        },
        "validation_rules": [
            "Visual embeddings enable finding similar products",
            "Used internally by detect_product_from_image"
        ]
    },
    
    # =========================================================================
    # PAYMENT WORKER TOOLS
    # =========================================================================
    "calculate_delivery_fee": {
        "worker": "payment_worker",
        "purpose": "Calculate delivery cost based on destination address",
        "expected_output": "Fee amount with breakdown (zone, distance)",
        "success_indicators": ["fee", "₦", "delivery", "NGN"],
        "failure_modes": {
            "Cannot geocode": "Ask customer for more specific address with landmarks",
            "Outside delivery area": "Inform customer we cannot deliver to that location",
            "Error": "Logistics MCP may be down - offer pickup option"
        },
        "validation_rules": [
            "Delivery fee must be displayed to customer before payment",
            "Fee tiers: Within 8.7km=₦1,500, 8.7-12.2km=₦2,000, 12.2-13.1km=₦2,500, >13.1km=₦3,000"
        ]
    },
    
    "generate_payment_link": {
        "worker": "payment_worker",
        "purpose": "Generate Paystack payment URL for order",
        "expected_output": "Payment URL with amount, reference, and delivery details",
        "success_indicators": ["paystack", "payment", "link", "http", "₦"],
        "failure_modes": {
            "Missing delivery details": "Request name, phone, address from customer first",
            "Invalid amount": "Verify order total calculation",
            "Paystack error": "Payment MCP may be down - escalate to manager"
        },
        "validation_rules": [
            "Payment link MUST include correct total (items + delivery fee)",
            "Delivery details MUST be collected before generating link (unless pickup)"
        ]
    },
    
    "create_order_record": {
        "worker": "payment_worker",
        "purpose": "Create order record in POS system",
        "expected_output": "Order ID or confirmation",
        "success_indicators": ["order", "created", "id", "success"],
        "failure_modes": {
            "Failed to create": "POS MCP may be down - retry or log manually",
            "Invalid data": "Verify all order fields are populated"
        },
        "validation_rules": [
            "Order creation should precede payment link generation",
            "Order record enables tracking and fulfillment"
        ]
    },
    
    "validate_and_extract_delivery": {
        "worker": "payment_worker",
        "purpose": "Extract delivery details (name, phone, address) from customer message",
        "expected_output": "Extracted fields with validation status",
        "success_indicators": ["extracted", "name", "phone", "address"],
        "failure_modes": {
            "Incomplete extraction": "Ask customer for missing fields specifically",
            "Invalid phone": "Request valid Nigerian phone format"
        },
        "validation_rules": [
            "All required fields: name, phone, address",
            "Phone must be valid Nigerian format (0xxx, +234xxx)"
        ]
    },
    
    "check_delivery_ready": {
        "worker": "payment_worker",
        "purpose": "Verify order has all required delivery details before payment",
        "expected_output": "Ready status with any missing fields listed",
        "success_indicators": ["ready", "valid", "complete"],
        "failure_modes": {
            "Not ready": "List missing fields and request from customer"
        },
        "validation_rules": [
            "Pickup orders only need name + phone",
            "Delivery orders need name, phone, address"
        ]
    },
    
    "request_delivery_details": {
        "worker": "payment_worker",
        "purpose": "Generate friendly message requesting delivery info from customer",
        "expected_output": "Formatted request message",
        "success_indicators": ["provide", "name", "phone", "address"],
        "failure_modes": {},
        "validation_rules": [
            "This is a prompt template - always succeeds",
            "Response asking for details is VALID (not a failure)"
        ]
    },
    
    # =========================================================================
    # SUPPORT WORKER TOOLS
    # =========================================================================
    "lookup_order_history": {
        "worker": "support_worker",
        "purpose": "Fetch recent orders for customer to understand complaint context",
        "expected_output": "List of recent orders with status",
        "success_indicators": ["order", "₦", "status"],
        "failure_modes": {
            "No orders found": "Customer may be new - ask for order details",
            "Database error": "Ask customer for order number manually"
        },
        "validation_rules": [
            "Order history helps understand complaint context",
            "Reference specific orders when addressing issues"
        ]
    },
    
    "create_support_ticket": {
        "worker": "support_worker",
        "purpose": "Create tracking ticket for customer issue",
        "expected_output": "Ticket ID confirmation",
        "success_indicators": ["ticket", "created", "#", "id"],
        "failure_modes": {
            "Failed to create": "Log issue manually and apologize"
        },
        "validation_rules": [
            "Every new complaint should get a ticket",
            "Ticket ID should be communicated to customer for reference"
        ]
    },
    
    "escalate_to_manager": {
        "worker": "support_worker",
        "purpose": "Escalate unresolvable issue to manager",
        "expected_output": "Confirmation of escalation with ticket reference",
        "success_indicators": ["escalated", "manager", "contact"],
        "failure_modes": {
            "Admin not configured": "Inform customer issue is logged, will follow up",
            "Send failed": "Retry or log for manual follow-up"
        },
        "validation_rules": [
            "After escalation, stop handling the issue (manager takes over)",
            "Inform customer that manager will contact them directly"
        ]
    },
    
    # =========================================================================
    # ADMIN WORKER TOOLS
    # =========================================================================
    "generate_comprehensive_report": {
        "worker": "admin_worker",
        "purpose": "Generate business report with PDF output",
        "expected_output": "Report file path and summary metrics",
        "success_indicators": ["report", "generated", ".pdf", "period"],
        "failure_modes": {
            "No data": "Specify valid date range with activity",
            "Generation failed": "Check database connectivity"
        },
        "validation_rules": [
            "Report should include key metrics: orders, revenue, customers",
            "PDF file should be generated successfully"
        ]
    },
    
    "list_pending_approvals": {
        "worker": "admin_worker",
        "purpose": "Show orders awaiting manager approval (>₦25,000)",
        "expected_output": "List of pending orders with amounts",
        "success_indicators": ["pending", "approval", "₦"],
        "failure_modes": {
            "No pending": "Inform manager there are no orders awaiting approval"
        },
        "validation_rules": [
            "High-value orders (>₦25,000) require approval",
            "Show customer ID and order amount"
        ]
    },
    
    "approve_order": {
        "worker": "admin_worker",
        "purpose": "Approve a pending high-value order",
        "expected_output": "Approval confirmation, customer notified",
        "success_indicators": ["approved", "✅", "confirmed"],
        "failure_modes": {
            "Not found": "Verify customer ID from pending list",
            "Ambiguous": "Multiple pending - specify which customer"
        },
        "validation_rules": [
            "Only admins can approve orders",
            "Customer should receive notification after approval"
        ]
    },
    
    "reject_order": {
        "worker": "admin_worker",
        "purpose": "Reject a pending order with reason",
        "expected_output": "Rejection confirmation, customer notified with reason",
        "success_indicators": ["rejected", "🚫", "reason"],
        "failure_modes": {
            "Not found": "Verify customer ID from pending list"
        },
        "validation_rules": [
            "Rejection must include a reason",
            "Customer should be informed of how to proceed"
        ]
    },
    
    "relay_message_to_customer": {
        "worker": "admin_worker",
        "purpose": "Send WhatsApp message to customer",
        "expected_output": "Send confirmation",
        "success_indicators": ["sent", "message", "✅"],
        "failure_modes": {
            "Invalid ID": "Verify customer phone number format",
            "Send failed": "Check Meta service connectivity"
        },
        "validation_rules": [
            "Message should be professional and helpful",
            "Customer ID should be valid phone number"
        ]
    },
    
    "get_incident_context": {
        "worker": "admin_worker",
        "purpose": "Retrieve incident details for manager review",
        "expected_output": "STAR format incident report",
        "success_indicators": ["incident", "situation", "task", "action", "result"],
        "failure_modes": {
            "Not found": "Verify incident ID or search by customer"
        },
        "validation_rules": [
            "Provide full STAR context for informed decision-making"
        ]
    },
    
    "resolve_incident": {
        "worker": "admin_worker",
        "purpose": "Mark incident as resolved with resolution note",
        "expected_output": "Resolution confirmation",
        "success_indicators": ["resolved", "RESOLVED", "✅"],
        "failure_modes": {
            "Not found": "Verify incident ID"
        },
        "validation_rules": [
            "Resolution should include what action was taken"
        ]
    },
    
    "report_incident": {
        "worker": "admin_worker",
        "purpose": "Report incident to manager using STAR methodology",
        "expected_output": "Report sent confirmation",
        "success_indicators": ["report", "sent", "manager"],
        "failure_modes": {
            "Admin not configured": "Log incident for manual review"
        },
        "validation_rules": [
            "Include all STAR fields: Situation, Task, Action, Result"
        ]
    },
    
    "get_top_customers": {
        "worker": "admin_worker",
        "purpose": "Get top customers by lead score/purchases",
        "expected_output": "Customer ranking table",
        "success_indicators": ["customer", "rank", "spent", "score"],
        "failure_modes": {
            "No data": "Check date range or expand to 'all' period"
        },
        "validation_rules": [
            "Rankings should be based on RFM scoring",
            "Mask customer IDs for privacy"
        ]
    },
    
    "generate_weekly_report": {
        "worker": "admin_worker",
        "purpose": "Generate weekly business report (wrapper for comprehensive report)",
        "expected_output": "Report file path and weekly summary",
        "success_indicators": ["report", "generated", "week", ".pdf"],
        "failure_modes": {
            "No data": "No activity in the specified week",
            "Generation failed": "Check database connectivity"
        },
        "validation_rules": [
            "Weekly report is a convenience wrapper",
            "Same validation as comprehensive report"
        ]
    },
}


# =============================================================================
# WORKER AUDIT RULES (TIERED STRICTNESS)
# =============================================================================

WORKER_AUDIT_RULES: Dict[str, str] = {
    "sales_worker": """### STRICT ANTI-HALLUCINATION MODE
1. **Product recommendations MUST have tool evidence** - Every product name MUST appear in tool output
2. **Prices MUST exactly match tool evidence** (no rounding, no guessing)
3. **Category flexibility**: cream ≈ lotion ≈ moisturizer ≈ body milk (same brand = OK)
4. **Visual search matches are VALID evidence sources**

### APPROVED WITHOUT TOOL EVIDENCE (No hallucination risk):
5. **Non-skincare apologetic responses** - If customer asks for makeup/SPMU/accessories:
   - Response says "we only handle skincare through this channel"
   - Promises manager follow-up
   - Offers to show skincare instead
   - This is VALID without tool call (no products to look up)

6. **Alternative suggestions FROM tool evidence** - If search returns "No results" but suggests alternatives:
   - Worker CAN recommend the alternatives shown in tool output
   - These are NOT hallucinations - they came from the tool
   - Example: Search for "CeraVe" returns "No exact match. Similar: Nivea Lotion ₦4,500" → Nivea is VALID

7. **Order flow confirmations** - "Added X to order", "Your total is Y" based on prior evidence

REJECT if: Product names or prices don't match evidence AND response is NOT an approved exception""",

    "payment_worker": """### MODERATE VALIDATION
1. Payment link must contain valid URL (paystack.com or similar)
2. Amount must be correctly calculated (items + delivery fee)
3. Delivery details collection is VALID even without tool evidence (it's a request to customer)
4. Fee calculation must match tool output
5. Order creation confirmation is expected before payment link
REJECT if: Invalid payment URL, incorrect amount, or missing delivery validation""",

    "support_worker": """### EMPATHY-FOCUSED VALIDATION
1. Response should acknowledge customer's feelings FIRST
2. Ticket creation confirmation is expected for complaints
3. Escalation messages should confirm manager will contact
4. Order history lookup is helpful but not required
5. Tone should be apologetic and reassuring
REJECT if: Response is cold/dismissive, or lacks empathy acknowledgment""",

    "admin_worker": """### TRUST MODE (PRIVILEGED USER)
1. Admin context = pre-verified manager user
2. Report generation, approvals, rejections are administrative actions
3. Customer messaging should be professional
4. Minimal validation - focus on action completion
REJECT if: Clear error or incomplete action"""
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_tool_knowledge(tool_name: str) -> Dict[str, Any]:
    """Get knowledge for a specific tool."""
    # Handle tool name variations (some have _tool suffix)
    clean_name = tool_name.replace("_tool", "")
    return TOOL_KNOWLEDGE.get(clean_name, TOOL_KNOWLEDGE.get(tool_name, {}))


def get_tools_for_worker(worker_name: str) -> List[str]:
    """Get all tools available to a specific worker."""
    return [name for name, info in TOOL_KNOWLEDGE.items() if info.get("worker") == worker_name]


def get_tool_validation_prompt(called_tools: List[str]) -> str:
    """
    Generate validation prompt section for the tools that were actually called.
    This keeps the prompt focused and avoids bloat.
    """
    if not called_tools:
        return "### NO TOOLS WERE CALLED\nResponse should be a greeting or clarifying question."
    
    prompt_parts = ["### TOOL VALIDATION REFERENCE"]
    
    for tool_name in called_tools:
        info = get_tool_knowledge(tool_name)
        if not info:
            continue
            
        prompt_parts.append(f"\n**{tool_name}**")
        prompt_parts.append(f"- Purpose: {info.get('purpose', 'Unknown')}")
        prompt_parts.append(f"- Expected: {info.get('expected_output', 'Unknown')}")
        prompt_parts.append(f"- Success if contains: {', '.join(info.get('success_indicators', []))}")
        
        failures = info.get("failure_modes", {})
        if failures:
            prompt_parts.append("- Failure corrections:")
            for mode, fix in failures.items():
                prompt_parts.append(f"  • {mode}: {fix}")
    
    return "\n".join(prompt_parts)


def get_worker_audit_rules(worker_name: str) -> str:
    """Get the audit rules for a specific worker type."""
    return WORKER_AUDIT_RULES.get(worker_name, "Standard validation - verify response matches evidence.")
