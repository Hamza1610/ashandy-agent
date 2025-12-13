from app.state.agent_state import AgentState
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage
from app.utils.config import settings
import logging
import json

logger = logging.getLogger(__name__)

async def reviewer_agent_node(state: AgentState):
    """
    Reviewer Agent: The Internal Auditor.
    
    Responsibilities:
    1. Validates the LAST WORKER'S output against the Task Description.
    2. Checks for hallucinations, math errors, and missing information.
    3. Provides constructive critique if rejected.
    4. Auto-corrects trivial formatting issues if high confidence.
    
    Inputs:
    - state['current_task']
    - state['worker_result']
    - state['retry_counts']
    
    Outputs:
    - task_statuses[task_id] -> "approved" | "failed"
    - reviewer_critique -> Feedback
    """
    try:
        # 1. Gather Context
        plan = state.get("plan", [])
        idx = state.get("current_step_index", 0)
        
        if not plan or idx >= len(plan):
            return {"error": "Reviewer called with no active task."}
            
        current_step = plan[idx] # WARNING: This uses global IDX. Reviewer MUST use specific logic too.
        # But for generic Reviewer node aliased as 'sales_reviewer' etc, we need to know WHICH task.
        # For now, let's assume specific reviewers or the single node finds the "In Progress" task for its domain.
        
        # FIX: Find the task being reviewed (Status = in_progress or reviewing)
        # Assuming the worker just finished, status might still be "in_progress" (set by Dispatcher).
        # We need a way to link Reviewer Execution to Task ID.
        # If we use Aliased Nodes (sales_reviewer), we search for sales task.
        
        task_id = None
        for step in plan:
             # Heuristic: If status is 'in_progress', it's ready for review.
             # Only one task should be in_progress per worker type in our simplified parallel model.
             if task_statuses.get(step["id"]) == "in_progress":
                 task_id = step["id"]
                 current_step = step
                 break
        
        if not task_id:
             return {"error": "Reviewer found no task to review."}

        task_desc = current_step.get("task", "")
        worker_result = state.get("worker_outputs", {}).get(task_id, "")
        
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
        
        # 4. Construct Prompt
        system_prompt = f"""You are the **Quality Assurance Auditor** for an AI Commerce Agent.
Your job is to strictly verify the "Worker Output" against the "Task Description".

**Task:** "{task_desc}"

**Worker Output:** 
{worker_result}

**Verification Criteria:**
1. **Accuracy**: Are facts, prices, and math correct?
2. **Completeness**: Did the worker answer the ENTIRE task?
3. **Safety**: No hallucinations or dangerous content.
4. **Format**: Is the output clean and readable?

**Output JSON Format (Strict):**
{{
    "verdict": "APPROVE" | "REJECT",
    "critique": "Exact reason for rejection (if REJECT). Be specific and constructive.",
    "correction": "Optional corrected version (if minor formatting error)"
}}

**Rules:**
- If the output is "good enough", APPROVE. Do not be nitpicky about style unless it affects clarity.
- If REJECT, your `critique` will be shown to the worker to fix it.
- If the output creates a broken user experience (e.g., empty string, code trace), REJECT.
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
