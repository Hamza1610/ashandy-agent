from app.state.agent_state import AgentState
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from app.utils.config import settings
import logging
import json

logger = logging.getLogger(__name__)

async def reviewer_agent_node(state: AgentState, worker_scope: str = None):
    """
    Reviewer Agent: The Internal Auditor.
    
    Args:
        state: The AgentState
        worker_scope: Optional filter (e.g., "sales_worker"). 
                      If provided, checks ONLY tasks for this worker.
    """
    try:
        # 1. Gather Context
        plan = state.get("plan", [])
        idx = state.get("current_step_index", 0)
        task_statuses = state.get("task_statuses", {})
        
        if not plan:
            return {"error": "Reviewer called with no plan."}
            
        # FIX: Find the task being reviewed (Status = in_progress or reviewing)
        # We start searching from the 'current_step_index' or just scan all?
        # Scanning is safer for parallel flows.
        
        task_id = None
        current_step = None
        
        for step in plan:
             s_id = step.get("id")
             s_worker = step.get("worker")
             status = task_statuses.get(s_id)
             
             # If we have a scope, IGNORE tasks not for this worker
             if worker_scope and s_worker != worker_scope:
                 continue
                 
             # Heuristic: If status is 'in_progress' or 'reviewing', it's the target.
             if status in ["in_progress", "reviewing"]:
                 task_id = s_id
                 current_step = step
                 break
        
        if not task_id:
             # Just pass through if nothing to review (could happen in complex graph edges)
             return {}

        
        if not task_id:
             return {"error": "Reviewer found no task to review."}

        task_desc = current_step.get("task", "")
        worker_result = state.get("worker_outputs", {}).get(task_id, "")
        
        # Evidence Retrieval
        tool_evidence = state.get("worker_tool_outputs", {}).get(task_id, [])
        evidence_block = ""
        if tool_evidence:
             evidence_block = "### 🔍 DATABASE EVIDENCE (GROUND TRUTH):\n"
             for item in tool_evidence:
                 evidence_block += f"- Tool: {item['tool']}\n  Args: {item['args']}\n  Output: {item['output']}\n"
        else:
             evidence_block = "### ⚠️ NO TOOL EVIDENCE AVAILABLE (Verify Logic Only)"

        # 2. Check Retry Count (Deadlock Prevention)
        retry_counts = state.get("retry_counts", {})
        current_retries = retry_counts.get(task_id, 0)
        
        MAX_RETRIES = 2
        if current_retries >= MAX_RETRIES:
            logger.warning(f"Reviewer: Task {task_id} exceeded max retries ({MAX_RETRIES}). FAILING.")
            # Update status to failed
            task_statuses = state.get("task_statuses", {})
            task_statuses[task_id] = "failed"
            return {
                "task_statuses": task_statuses,
                "reviewer_critique": "Max retries exceeded. Manual intervention required."
            }

        # 3. Setup LLM (Speed Stack: Llama 3.1 8B Instant)
        llm = ChatGroq(
            temperature=0.1, # strict
            groq_api_key=settings.LLAMA_API_KEY,
            model_name="llama-3.1-8b-instant",
            response_format={"type": "json_object"}
        )
        
        # 4. Construct Prompt (High-Level Chain-of-Thought for 8B)
        system_prompt = f"""You are the **Quality Assurance Auditor** for an AI Commerce Agent.
Your Goal: Strictly verify the 'Worker Output' against the 'Task' and 'Database Evidence'.

### 1. INPUT DATA
**Task:** "{task_desc}"

**Worker Output (The Draft):** 
"{worker_result}"

{evidence_block}

### 2. AUDIT INSTRUCTIONS
Check these 3 dimensions. If any fail, REJECT.

**A. Accuracy (Fact Check)**
- Does the Output match the Evidence? 
- *Bad:* Evidence says Price is 5000, Output says 4000. -> REJECT.
- *Good:* Evidence says Stock is 0, Output says "Out of Stock". -> APPROVE.
- *If No Evidence:* Trust the logic, but flag hallucinations.

**B. Completeness**
- Did the worker answer the *specific* task? 
- *Bad:* Task="Get Price", Output="Hello". -> REJECT.

**C. Safety & Format**
- Is it clean text (no JSON/Code traces)?
- Is it polite?

### 3. OUTPUT FORMAT (JSON ONLY)
{{
    "verdict": "APPROVE" | "REJECT",
    "critique": "Exact reason for rejection (if REJECT). Be specific about the mismatch.",
    "correction": "Optional corrected version"
}}

**Tips:**
- If the output is "No active task", REJECT.
- If the output contains error traces, REJECT.
- If the output matches evidence, APPROVE.
"""

        messages = [SystemMessage(content=system_prompt)]
        
        # 5. Invoke
        response = await llm.ainvoke(messages)
        content = response.content
        logger.info(f"Reviewer Output: {content}")
        
        # 6. Parse
        try:
            result_json = json.loads(content)
        except json.JSONDecodeError:
            # Fallback for bad JSON
            if "APPROVE" in content:
                result_json = {"verdict": "APPROVE"}
            else:
                result_json = {"verdict": "REJECT", "critique": "Invalid JSON format from worker."}

        verdict = result_json.get("verdict", "REJECT").upper()
        critique = result_json.get("critique", "")
        
        task_statuses = state.get("task_statuses", {})
        if not task_statuses: task_statuses = {}

        if verdict == "APPROVE":
            logger.info(f"Reviewer: Task {task_id} APPROVED.")
            task_statuses[task_id] = "approved"
            
            # Reset retry count on success
            retry_counts[task_id] = 0
            
            return {
                "task_statuses": task_statuses,
                "retry_counts": retry_counts,
                "reviewer_critique": None # Clear critique
            }
        else:
            logger.warning(f"Reviewer: Task {task_id} REJECTED. Reason: {critique}")
            task_statuses[task_id] = "reviewing" # Sent back for review/fix
            
            # Increment Retry Count
            retry_counts[task_id] = current_retries + 1
            
            return {
                "task_statuses": task_statuses,
                "retry_counts": retry_counts,
                "reviewer_critique": critique
            }

    except Exception as e:
        logger.error(f"Reviewer Error: {e}", exc_info=True)
        # Default to reject to be safe
        return {"reviewer_critique": f"System Error in Reviewer: {str(e)}"}
