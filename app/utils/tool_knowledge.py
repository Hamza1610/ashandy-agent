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
    # CART MANAGEMENT TOOLS (Sales Worker)
    # =========================================================================
    "add_to_cart": {
        "worker": "sales_worker",
        "purpose": "Add product to shopping cart with quantity",
        "expected_output": "Confirmation with product name, quantity, and price",
        "success_indicators": ["Added", "✅", "cart", "₦"],
        "failure_modes": {
            "Product not found": "Search for product first to get accurate name and price",
            "Invalid quantity": "Quantity must be greater than 0"
        },
        "validation_rules": [
            "Cart additions are VALID evidence of order progress",
            "Confirmation message with product details is acceptable output"
        ]
    },
    
    "remove_from_cart": {
        "worker": "sales_worker",
        "purpose": "Remove product from shopping cart",
        "expected_output": "Removal confirmation",
        "success_indicators": ["Removed", "✅"],
        "failure_modes": {},
        "validation_rules": [
            "Removal confirmations are valid"
        ]
    },
    
    "update_cart_quantity": {
        "worker": "sales_worker",
        "purpose": "Update quantity of item in cart",
        "expected_output": "Update confirmation with new quantity",
        "success_indicators": ["Updated", "quantity", "✅"],
        "failure_modes": {
            "Quantity cannot be negative": "Use valid positive quantity or 0 to remove"
        },
        "validation_rules": [
            "Quantity updates are valid cart management actions"
        ]
    },
    
    "get_cart_summary": {
        "worker": "sales_worker",
        "purpose": "Show current cart contents and total",
        "expected_output": "Cart items list with subtotal",
        "success_indicators": ["Cart", "Subtotal", "₦", "total"],
        "failure_modes": {},
        "validation_rules": [
            "Cart summaries show order state - VALID evidence",
            "May include delivery fee if location provided"
        ]
    },
    
    "clear_cart": {
        "worker": "sales_worker",
        "purpose": "Empty all items from cart",
        "expected_output": "Clear confirmation",
        "success_indicators": ["cleared", "✅"],
        "failure_modes": {},
        "validation_rules": [
            "Cart clearing is valid operation"
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
            "Returns formatted text summary and PDF file path"
        ]
    },
    
    "generate_weekly_report": {
        "worker": "admin_worker",
        "purpose": "Generate weekly business report (wrapper for comprehensive report)",
        "expected_output": "PDF report file path and summary statistics",
        "success_indicators": ["Report generated", "PDF", "Week"],
        "failure_modes": {
            "Data unavailable": "No data for the specified week",
            "PDF error": "Check fpdf installation and permissions"
        },
        "validation_rules": [
            "Wrapper function that calls generate_comprehensive_report",
            "Automatically calculates week range from start date",  
            "Returns same format as comprehensive report"
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
    
    "verify_payment": {
        "worker": "payment_worker",
        "purpose": "Check status of a payment transaction",
        "expected_output": "Payment status (success, pending, failed)",
        "success_indicators": ["success", "paid", "verified", "status"],
        "failure_modes": {
            "Not found": "Verify payment reference",
            "Still pending": "Ask customer to complete payment"
        },
        "validation_rules": [
            "Payment verification is valid tool use"
        ]
    },
    
    "create_order_from_cart": {
        "worker": "payment_worker",
        "purpose": "Convert cart items to structured order data",
        "expected_output": "Order data with items, subtotal, delivery type",
        "success_indicators": ["items", "subtotal", "₦"],
        "failure_modes": {
            "Cart is empty": "Customer needs to add items first"
        },
        "validation_rules": [
            "Order creation from cart is VALID evidence"
        ]
    },
    
    "get_cart_total": {
        "worker": "payment_worker",
        "purpose": "Calculate cart total with optional delivery fee",
        "expected_output": "Cart summary with subtotal and optional delivery calculation",
        "success_indicators": ["Subtotal", "₦", "Cart", "Delivery"],
        "failure_modes": {},
        "validation_rules": [
            "Cart totals are valid order evidence",
            "Delivery fee may be included if location provided"
        ]
    },
    
    "validate_order_ready": {
        "worker": "payment_worker",
        "purpose": "Check if order has required items for payment",
        "expected_output": "Ready status with any issues listed",
        "success_indicators": ["ready", "valid"],
        "failure_modes": {
            "Cart empty": "Items needed before checkout",
            "Invalid items": "Check product data"
        },
        "validation_rules": [
            "Order validation is valid checkout step"
        ]
    },
    
    "get_order_total_with_delivery": {
        "worker": "payment_worker",
        "purpose": "Calculate complete order total including cart and delivery fee",
        "expected_output": "Complete breakdown showing cart subtotal, delivery fee, and grand total",
        "success_indicators": ["Subtotal", "Delivery", "GRAND TOTAL", "₦"],
        "failure_modes": {
            "Cart empty": "Need items in cart first",
            "Delivery location missing": "Need delivery address for fee calculation"
        },
        "validation_rules": [
            "Complete order totals with delivery are VALID and PREFERRED for checkout",
            "Shows customer exact amount they'll pay"
        ]
    },
    
    "format_order_summary": {
        "worker": "payment_worker",
        "purpose": "Format order total data into customer-friendly display",
        "expected_output": "Formatted order breakdown",
        "success_indicators": ["ORDER SUMMARY", "Items", "₦"],
        "failure_modes": {},
        "validation_rules": [
            "Formatting utility - output is valid"
        ]
    },
    
    "get_manual_payment_instructions": {
        "worker": "payment_worker",
        "purpose": "Provide bank transfer instructions when Paystack fails",
        "expected_output": "Bank details with account number, amount, reference",
        "success_indicators": ["Bank Transfer", "Account", "Reference", "₦"],
        "failure_modes": {},
        "validation_rules": [
            "Manual payment fallback is VALID when payment link fails",
            "Provides alternative payment method"
        ]
    },
    
    "check_api_health": {
        "worker": "payment_worker",
        "purpose": "Check if payment APIs are operational",
        "expected_output": "Status message about API availability",
        "success_indicators": ["operational", "available", "status"],
        "failure_modes": {},
        "validation_rules": [
            "Health check is valid diagnostic tool"
        ]
    },
    
    "notify_manager": {
        "worker": "admin_worker",
        "purpose": "Send SMS notification to manager about new order",
        "expected_output": "Confirmation that manager was notified",
        "success_indicators": ["Manager notified", "SMS sent", "Order"],
        "failure_modes": {
            "SMS not configured": "Twilio credentials missing - check .env",
            "Manager phone missing": "Set ADMIN_PHONE_NUMBERS in settings"
        },
        "validation_rules": [
            "Tool is for automated notifications after successful orders",
            "Manager should receive order details and delivery info"
        ]
    },
    
    "get_pending_manual_payments": {
        "worker": "admin_worker",
        "purpose": "List customers awaiting manual payment verification",
        "expected_output": "List of pending payments with customer, amount, reference",
        "success_indicators": ["Pending", "Manual Payments", "₦"],
        "failure_modes": {
            "No pending": "No manual payments to review - this is normal"
        },
        "validation_rules": [
            "Empty list is valid - means no pending verifications"
        ]
    },
    
    "confirm_manual_payment": {
        "worker": "admin_worker",
        "purpose": "Confirm bank transfer payment after verification",
        "expected_output": "Confirmation with order update and customer notification",
        "success_indicators": ["confirmed", "✅", "Customer notified", "PAID"],
        "failure_modes": {
            "Amount mismatch": "Verify amount matches order total exactly",
            "Not found": "Check customer ID and reference are correct"
        },
        "validation_rules": [
            "Requires exact amount match to prevent errors",
            "Automatically notifies customer via WhatsApp"
        ]
    },
    
    "reject_manual_payment": {
        "worker": "admin_worker",
        "purpose": "Reject invalid/fake manual payment",
        "expected_output": "Rejection confirmation with customer notification",
        "success_indicators": ["rejected", "❌", "Customer notified"],
        "failure_modes": {},
        "validation_rules": [
            "Requires reason to be provided to customer",
            "Customer is automatically notified of rejection"
        ]
    },
    
    "get_recent_orders": {
        "worker": "admin_worker",
        "purpose": "View recent orders within time period",
        "expected_output": "List of orders with status and details",
        "success_indicators": ["Recent Orders", "Order #", "₦"],
        "failure_modes": {
            "No orders": "No orders in specified time period"
        },
        "validation_rules": [
            "Empty result is valid - no orders in period"
        ]
    },
    
    "search_order_by_customer": {
        "worker": "admin_worker",
        "purpose": "Find all orders for specific customer",
        "expected_output": "Customer's order history",
        "success_indicators": ["Order History", "Total Paid", "₦"],
        "failure_modes": {
            "Not found": "No orders for this customer - may be new"
        },
        "validation_rules": [
            "Phone number is normalized automatically",
            "Shows total spending history"
        ]
    },
    
    "view_order_details": {
        "worker": "admin_worker",
        "purpose": "Get complete details of specific order",
        "expected_output": "Full order info including delivery and payment status",
        "success_indicators": ["Order #", "Customer", "Delivery Details"],
        "failure_modes": {
            "Not found": "Order ID doesn't exist"
        },
        "validation_rules": [
            "Shows complete order lifecycle"
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
    
    "update_incident_star": {
        "worker": "support_worker",
        "purpose": "Log Task, Action, Result fields for STAR incident tracking",
        "expected_output": "Confirmation that STAR fields were updated",
        "success_indicators": ["updated", "✅", "incident"],
        "failure_modes": {
            "Incident not found": "Verify incident_id is correct"
        },
        "validation_rules": [
            "MUST be called after creating ticket to log task and initial action",
            "Should be updated when manager responds with result",
            "Provides complete audit trail for quality improvement",
            "Every support action should be logged for accountability"
        ]
    },
    
    "relay_to_manager": {
        "worker": "support_worker",
        "purpose": "Send question to manager via WhatsApp and notify customer to expect response",
        "expected_output": "Confirmation message to send to customer",
        "success_indicators": ["contacted", "team", "update", "ticket"],
        "failure_modes": {
            "Manager not configured": "Admin phone not set - ticket still created"
        },
        "validation_rules": [
            "Use for order status queries, refund requests, or manager decisions",
            "Include suggested_responses to guide manager's answer format",
            "Customer should be told to expect manager update",
            "Ticket number should be provided for customer reference"
        ]
    },
    
    "confirm_customer_resolution": {
        "worker": "support_worker",
        "purpose": "Mark incident as RESOLVED when customer confirms issue is fixed",
        "expected_output": "Confirmation that ticket was marked resolved",
        "success_indicators": ["RESOLVED", "✅", "marked"],
        "failure_modes": {
            "Not confirmed": "Customer must explicitly confirm resolution",
            "Already escalated": "Cannot resolve ESCALATED incidents (manager handles)"
        },
        "validation_rules": [
            "ONLY use when customer explicitly confirms ('Thanks!', 'All good!', etc.)",
            "ONLY for simple issues (tracking, status, general questions)",
            "DO NOT use for refunds (must stay ESCALATED until refund processes)",
            "DO NOT use for damage claims or disputes",
            "Requires customer_confirmed=True to proceed"
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

7. **Cart management operations** - add_to_cart, remove_from_cart, get_cart_summary outputs are VALID evidence:
   - "Added X to cart" confirmations are valid
   - Cart totals with delivery fees are valid
   - Quantity updates are valid

REJECT if: Product names or prices don't match evidence AND response is NOT an approved exception""",

    "payment_worker": """### MODERATE VALIDATION
1. Payment link must contain valid URL (paystack.com or similar) OR manual payment instructions if API failed
2. Amount must be correctly calculated (cart items + delivery fee)
3. Delivery details collection is VALID even without tool evidence (it's a request to customer)
4. Fee calculation must match tool output OR be calculated by get_order_total_with_delivery
5. Order creation from cart (create_order_from_cart) is VALID evidence
6. Cart total summaries (get_cart_total, get_order_total_with_delivery) are VALID evidence
7. Manual payment fallback is ACCEPTABLE when payment link fails after retries
REJECT if: Invalid payment amount, or missing required delivery validation""",

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
