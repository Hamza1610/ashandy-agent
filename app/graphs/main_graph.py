from langgraph.graph import StateGraph, END
from app.state.agent_state import AgentState
from app.agents.supervisor_agent import supervisor_agent_node, output_supervisor_node
from app.agents.planner_agent import planner_agent_node
from app.agents.sales_worker import sales_worker_node
from app.agents.admin_worker import admin_worker_node, admin_email_alert_node
from app.agents.payment_worker import payment_worker_node
from app.agents.reviewer_agent import reviewer_agent_node
from langchain_core.messages import AIMessage
import logging

logger = logging.getLogger(__name__)

# --- Dispatcher Logic ---

def dispatcher_node(state: AgentState):
    """
    Dispatcher: The Router & State Manager.
    Determines which tasks can run in parallel based on dependencies.
    """
    plan = state.get("plan", [])
    task_statuses = state.get("task_statuses", {})
    retry_counts = state.get("retry_counts", {})
    
    # 1. Identify Next Steps
    next_workers = []
    updated_statuses = task_statuses.copy()
    
    # Check if we are done
    # "failed" is terminal for that branch, "approved" is success.
    
    active_worker_types = set()
    
    logger.info(f"DEBUG DISPATCHER: Plan={len(plan)} Statuses={task_statuses}")
    
    for step in plan:
        id = step["id"]
        status = task_statuses.get(id, "pending")
        worker_type = step["worker"]
        
        logger.info(f"Dispatch Check Step {id}: Status={status}, Worker={worker_type}")
        
        # If Failed, do we stop everything? 
        # Plan says: "Graceful fail to user".
        if status == "failed":
            return {"error": f"Task {id} Failed after retries."} 

        if status == "pending" or status == "reviewing":
            # Check Dependencies
            deps = step.get("dependencies", [])
            # All deps must be approved
            deps_met = all(updated_statuses.get(d) == "approved" for d in deps)
            
            if deps_met:
                # CONSTRAINT: Only one task per worker type per turn (to simplify Worker "Find My Task" logic)
                if worker_type not in active_worker_types:
                    updated_statuses[id] = "in_progress" # Activate
                    next_workers.append(worker_type)
                    active_worker_types.add(worker_type)
                    logger.info(f"ACTIVATING Task {id} for {worker_type}")
    
    logger.info(f"DISPATCHER RETURNING: Next={next_workers}, UpdatedStatus={updated_statuses}")

    return {
        "task_statuses": updated_statuses, 
        "next_workers": next_workers # Temp key for router
    }

def dispatcher_edge(state: AgentState):
    """Routing logic for Dispatcher"""
    error = state.get("error")
    if error:
        return "end_fail"
        
    next_workers = state.get("next_workers", [])
    task_statuses = state.get("task_statuses", {})
    plan = state.get("plan", [])
    
    if not next_workers:
        # Check if really done
        all_complete = all(task_statuses.get(s["id"]) in ["approved", "failed"] for s in plan)
        if all_complete:
            return "output_supervisor"
        else:
            # If tasks pending but no workers? Deadlock or waiting for external event?
            # In this self-contained graph, it means Error or Deadlock.
            return "end_fail" # Safety Valve
            
    return next_workers

def supervisor_router(state: AgentState):
    verdict = state.get("supervisor_verdict", "ignore")
    if verdict == "safe":
        return "planner"
    elif verdict == "block":
        return "end_block" 
    else:
        return "end_ignore"
        
def output_supervisor_router(state: AgentState):
    verdict = state.get("supervisor_output_verdict", "safe")
    if verdict == "block":
        return "end_block"
    return END

# --- Graph Construction ---

workflow = StateGraph(AgentState)

# Nodes
workflow.add_node("supervisor", supervisor_agent_node)
workflow.add_node("planner", planner_agent_node)
workflow.add_node("dispatcher", dispatcher_node)

# Workers
workflow.add_node("sales_worker", sales_worker_node)
workflow.add_node("admin_worker", admin_worker_node)
workflow.add_node("payment_worker", payment_worker_node)
workflow.add_node("email_alert", admin_email_alert_node) # New Node

from functools import partial

# Reviewers (Aliased nodes for parallel wiring with specific scope)
workflow.add_node("sales_reviewer", partial(reviewer_agent_node, worker_scope="sales_worker"))
workflow.add_node("admin_reviewer", partial(reviewer_agent_node, worker_scope="admin_worker"))
workflow.add_node("payment_reviewer", partial(reviewer_agent_node, worker_scope="payment_worker"))

# Output Supervisor
workflow.add_node("output_supervisor", output_supervisor_node)

# Entry
workflow.set_entry_point("supervisor")

# Edges
workflow.add_conditional_edges(
    "supervisor",
    supervisor_router,
    {"planner": "planner", "end_block": END, "end_ignore": END}
)

workflow.add_edge("planner", "dispatcher")

# Dispatcher Fan-Out
workflow.add_conditional_edges(
    "dispatcher",
    dispatcher_edge,
    {
        "sales_worker": "sales_worker",
        "admin_worker": "admin_worker",
        "payment_worker": "payment_worker",
        "output_supervisor": "output_supervisor",
        "end_fail": "email_alert" 
    }
)

# Worker -> Reviewer
workflow.add_edge("sales_worker", "sales_reviewer")
workflow.add_edge("admin_worker", "admin_reviewer")
workflow.add_edge("payment_worker", "payment_reviewer")

# Reviewer -> Dispatcher (Loop)
workflow.add_edge("sales_reviewer", "dispatcher")
workflow.add_edge("admin_reviewer", "dispatcher")
workflow.add_edge("payment_reviewer", "dispatcher")

workflow.add_edge("email_alert", END)

# Output Supervisor
workflow.add_conditional_edges(
    "output_supervisor", 
    output_supervisor_router,
    {"end_block": END, END: END}
)

app = workflow.compile()
