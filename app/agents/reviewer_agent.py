"""
Reviewer Agent: Quality assurance auditor that validates worker outputs against evidence.
"""
from app.state.agent_state import AgentState
from app.services.llm_service import get_llm
from langchain_core.messages import SystemMessage
import logging
import json

logger = logging.getLogger(__name__)

MAX_RETRIES = 4  # 5 total attempts (1 initial + 4 retries) before escalation


async def reviewer_agent_node(state: AgentState, worker_scope: str = None):
    """Validates worker outputs against task requirements and tool evidence."""
    try:
        plan = state.get("plan", [])
        task_statuses = state.get("task_statuses", {})
        
        if not plan:
            return {"error": "Reviewer called with no plan."}
            
        # Find task being reviewed
        task_id = None
        current_step = None
        
        for step in plan:
            s_id = step.get("id")
            s_worker = step.get("worker")
            status = task_statuses.get(s_id)
            
            if worker_scope and s_worker != worker_scope:
                continue
                 
            if status in ["in_progress", "reviewing"]:
                task_id = s_id
                current_step = step
                break
        
        if not task_id:
            return {}

        task_desc = current_step.get("task", "")
        worker_result = state.get("worker_outputs", {}).get(task_id, "")
        
        # Build evidence block
        tool_evidence = state.get("worker_tool_outputs", {}).get(task_id, [])
        if tool_evidence:
            evidence_block = "### 🔍 DATABASE EVIDENCE:\n"
            for item in tool_evidence:
                evidence_block += f"- Tool: {item['tool']}\n  Args: {item['args']}\n  Output: {item['output']}\n"
        else:
            evidence_block = "### ⚠️ NO TOOL EVIDENCE AVAILABLE"

        # Check retry count
        retry_counts = state.get("retry_counts", {})
        current_retries = retry_counts.get(task_id, 0)
        
        if current_retries >= MAX_RETRIES:
            logger.warning(f"Reviewer: Task {task_id} exceeded max retries. FAILING.")
            task_statuses[task_id] = "failed"
            return {
                "task_statuses": task_statuses,
                "reviewer_critique": "Max retries exceeded. Manual intervention required."
            }

        llm = get_llm(model_type="fast", temperature=0.1, json_mode=True)
        
        system_prompt = f"""You are the Quality Assurance Auditor for an AI Commerce Agent.

### INPUT
**Task:** "{task_desc}"
**Worker Output:** "{worker_result}"
{evidence_block}

### AUDIT CRITERIA
A. **Accuracy**: Does output match evidence? Reject if prices/facts contradict evidence.
B. **Completeness**: Did worker attempt to address the task?
C. **Safety**: No JSON/code traces? Polite response?

### CRITICAL ANTI-HALLUCINATION RULES ⚠️
1. **NO TOOL EVIDENCE = REJECT** for product recommendations
   - If worker mentions product names or prices WITHOUT tool evidence → **REJECT**
   - Worker MUST have called search_products first
   - Only greetings and general responses can skip tools

2. **CATEGORY FLEXIBILITY** (IMPORTANT - avoid over-rejection):
   - If user asks for "X cream" and search returns "X lotion" → **APPROVE** (same brand, similar purpose)
   - Related product categories are acceptable: cream ≈ lotion ≈ moisturizer ≈ butter ≈ body milk
   - Face products when asked for body products (same brand) → **APPROVE with note**
   - Only REJECT if products are completely unrelated (e.g., asked for lipstick, got cleanser)
   - The goal is HELPFULNESS, not pedantic matching

3. **PRODUCT CLAIMS NEED PROOF**:
   - Every product name in output MUST appear in tool evidence
   - Every price ₦X,XXX MUST come from tool evidence
   - If output has products but no evidence block → **REJECT**

4. **PURCHASE CONFIRMATION EXCEPTIONS** (APPROVE without fresh tool evidence):
   - If task mentions "Process order" or "purchase confirmation" → Product was already verified
   - Requesting delivery details is VALID for payment flow
   - "To complete your order, please provide..." → APPROVE
   - Delivery fee calculations from calculate_delivery_fee → APPROVE
   - Payment link generation → APPROVE

5. **Valid exceptions** (can APPROVE without tool evidence):
   - Simple greetings/farewells
   - "I'll check for you" type responses
   - Error acknowledgments
   - **Delivery detail requests** ("Please provide your name/address/phone")
   - **Payment flow messages** (requesting info to generate payment link)

### OUTPUT (JSON ONLY)
{{"verdict": "APPROVE" | "REJECT", "critique": "Reason if REJECT", "correction": "Optional fix"}}

**Rules:**
- "No active task" → REJECT
- Error traces → REJECT
- Product names without tool evidence (in PRODUCT SEARCH tasks only) → REJECT
- Delivery detail requests in payment flow → **APPROVE**
- Matches evidence OR offers valid alternatives → APPROVE
"""

        response = await llm.ainvoke([SystemMessage(content=system_prompt)])
        content = response.content
        logger.info(f"Reviewer Output: {content}")
        
        try:
            result_json = json.loads(content)
        except json.JSONDecodeError:
            result_json = {"verdict": "APPROVE" if "APPROVE" in content else "REJECT", 
                          "critique": "Invalid JSON format from worker."}

        verdict = result_json.get("verdict", "REJECT").upper()
        critique = result_json.get("critique", "")
        
        if not task_statuses:
            task_statuses = {}

        if verdict == "APPROVE":
            logger.info(f"Reviewer: Task {task_id} APPROVED.")
            task_statuses[task_id] = "approved"
            retry_counts[task_id] = 0
            return {"task_statuses": task_statuses, "retry_counts": retry_counts, "reviewer_critique": None}
        else:
            logger.warning(f"Reviewer: Task {task_id} REJECTED. Reason: {critique}")
            task_statuses[task_id] = "reviewing"
            retry_counts[task_id] = current_retries + 1
            return {"task_statuses": task_statuses, "retry_counts": retry_counts, "reviewer_critique": critique}

    except Exception as e:
        logger.error(f"Reviewer Error: {e}", exc_info=True)
        return {"reviewer_critique": f"System Error in Reviewer: {str(e)}"}
