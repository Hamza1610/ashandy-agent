"""
Reviewer Agent: Quality assurance auditor that validates worker outputs against evidence.
"""
from app.state.agent_state import AgentState
from app.services.llm_service import get_llm
from langchain_core.messages import SystemMessage
import logging
import json

logger = logging.getLogger(__name__)

MAX_RETRIES = 2


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

### SPECIAL RULES (IMPORTANT)
- **SALES UPSELLING**: If exact product unavailable but worker recommended SIMILAR products, this is VALID behavior → APPROVE
- "Similar products" or "alternatives" when exact match not found → APPROVE
- Worker must NOT invent products not in evidence

### OUTPUT (JSON ONLY)
{{"verdict": "APPROVE" | "REJECT", "critique": "Reason if REJECT", "correction": "Optional fix"}}

**Rules:**
- "No active task" → REJECT
- Error traces → REJECT
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
