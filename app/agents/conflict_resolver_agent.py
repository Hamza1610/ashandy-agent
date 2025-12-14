"""
Conflict Resolver Agent: Detects and resolves semantic contradictions in worker outputs.
"""
from app.state.agent_state import AgentState
from app.services.llm_service import get_llm
from langchain_core.messages import SystemMessage, AIMessage
import logging
import json

logger = logging.getLogger(__name__)

async def conflict_resolver_node(state: AgentState):
    """
    Analyzes accumulated worker outputs for semantic conflicts.
    
    Priority Rules:
    1. PRICE: payment_worker > sales_worker > admin_worker
    2. STOCK: admin_worker > sales_worker
    3. POLICY: admin_worker > sales_worker
    """
    worker_outputs = state.get("worker_outputs", {})
    if not worker_outputs or len(worker_outputs) < 2:
        return {"conflict_resolution": "No conflict check needed (single output)."}
        
    # Prepare context for LLM
    outputs_str = ""
    for task_id, output in worker_outputs.items():
        outputs_str += f"[Task {task_id} Output]: {output}\n\n"
        
    llm = get_llm(model_type="fast", temperature=0.1, json_mode=True)
    
    system_prompt = f"""You are the Conflict Resolution Arbiter for Ashandy Cosmetics.

### INPUT
Multiple worker outputs executed in parallel:
{outputs_str}

### TASK
Detect semantic contradictions, specifically:
1. **Price Mismatch**: Different prices quoted for same item
2. **Stock Mismatch**: One says in-stock, other says out-of-stock
3. **Policy Mismatch**: Contradictory rules stated

### PRIORITY HIERARCHY
- **Prices/Delivery**: Trust `payment_worker`
- **Approvals/Stock**: Trust `admin_worker`
- **Product Info**: Trust `sales_worker`

### OUTPUT (JSON ONLY)
{{
    "has_conflict": boolean,
    "conflict_summary": "Description of conflict",
    "resolved_output": "Merged, consistent response (or null if no conflict)"
}}
"""

    try:
        response = await llm.ainvoke([SystemMessage(content=system_prompt)])
        content = response.content
        result = json.loads(content)
        
        if result.get("has_conflict"):
            logger.warning(f"⚔️ CONFLICT DETECTED: {result['conflict_summary']}")
            # Overwrite the latest message with the resolved output
            resolved_msg = result.get("resolved_output", "")
            return {
                "worker_result": resolved_msg,
                "messages": [AIMessage(content=resolved_msg)]
            }
        else:
            return {"conflict_resolution": "No conflict detected."}
            
    except Exception as e:
        logger.error(f"Conflict Resolver failed: {e}")
        return {"conflict_resolution": "Error in resolution."}
