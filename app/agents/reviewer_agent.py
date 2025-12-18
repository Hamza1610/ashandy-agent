"""
Reviewer Agent: Quality assurance auditor that validates worker outputs against evidence.

Enhanced with comprehensive tool knowledge for accurate validation across all workers.
"""
from app.state.agent_state import AgentState
from app.services.llm_service import get_llm
from app.utils.tool_knowledge import get_tool_validation_prompt, get_worker_audit_rules
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
        worker_type = current_step.get("worker", "unknown")
        worker_result = state.get("worker_outputs", {}).get(task_id, "")
        
        # Build evidence block with tool names for knowledge lookup
        tool_evidence = state.get("worker_tool_outputs", {}).get(task_id, [])
        called_tools = []
        
        if tool_evidence:
            evidence_block = "### 🔍 TOOL EVIDENCE:\n"
            for item in tool_evidence:
                tool_name = item.get('tool', 'unknown')
                called_tools.append(tool_name)
                evidence_block += f"- **{tool_name}**\n  Args: {item.get('args', {})}\n  Output: {item.get('output', '')}\n"
        else:
            evidence_block = "### ⚠️ NO TOOL EVIDENCE AVAILABLE"

        # Get dynamic tool knowledge for the tools that were actually called
        tool_validation_block = get_tool_validation_prompt(called_tools)
        
        # Get worker-specific audit rules (tiered strictness)
        worker_audit_rules = get_worker_audit_rules(worker_type)

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
**Worker:** {worker_type}
**Task:** "{task_desc}"
**Worker Output:** "{worker_result}"
{evidence_block}

{worker_audit_rules}

{tool_validation_block}

### UNIVERSAL AUDIT CRITERIA
A. **Accuracy**: Does output match evidence? Reject if prices/facts contradict evidence.
B. **Completeness**: Did worker attempt to address the task?
C. **Safety**: No JSON/code traces? Polite response?

### TOOL EVIDENCE RULES
1. **Check success indicators** for each tool called
2. **If tool failed**, the recommended correction is in the tool reference above
3. **Related categories are acceptable**: cream ≈ lotion ≈ moisturizer ≈ body milk (same brand = OK)
4. **Visual search matches** (detect_product_from_image) are VALID evidence sources

### VALID EXCEPTIONS (can APPROVE without fresh tool evidence)
- Simple greetings/farewells
- "I'll check for you" type responses
- Error acknowledgments
- Delivery detail requests ("Please provide your name/address/phone")
- Payment flow messages (requesting info to generate payment link)
- Support ticket confirmations
- Escalation confirmations ("Manager will contact you")
- **Non-skincare apologetic responses** (e.g., "we only handle skincare through this channel")
- **Alternative suggestions that appear in tool output** (not hallucination if from tool results)
- **Order confirmations** based on prior order state

### OUTPUT (JSON ONLY)
{{"verdict": "APPROVE" | "REJECT", "critique": "Reason if REJECT", "correction": "Specific fix based on tool failure modes"}}

**Critical:**
- Use tool failure modes above to provide ACCURATE corrections
- "No active task" → REJECT
- Error traces in output → REJECT
- Matches evidence OR is a valid exception → APPROVE
"""

        response = await llm.ainvoke([SystemMessage(content=system_prompt)])
        content = response.content
        logger.info(f"Reviewer Output ({worker_type}): {content}")
        
        try:
            result_json = json.loads(content)
        except json.JSONDecodeError:
            result_json = {"verdict": "APPROVE" if "APPROVE" in content else "REJECT", 
                          "critique": "Invalid JSON format from reviewer."}

        verdict = result_json.get("verdict", "REJECT").upper()
        critique = result_json.get("critique", "")
        correction = result_json.get("correction", "")
        
        # Include correction in critique for actionable feedback
        if correction and critique:
            critique = f"{critique} | Suggestion: {correction}"
        
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
