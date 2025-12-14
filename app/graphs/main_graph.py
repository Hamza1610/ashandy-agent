"""
Main Graph: LangGraph workflow orchestrating the agentic pipeline.
Supervisor → Planner → Dispatcher → Workers → Reviewers → Output
"""
from langgraph.graph import StateGraph, END
from app.state.agent_state import AgentState
from app.agents.supervisor_agent import supervisor_agent_node, output_supervisor_node
from app.agents.planner_agent import planner_agent_node
from app.agents.sales_worker import sales_worker_node
from app.agents.admin_worker import admin_worker_node, admin_email_alert_node
from app.agents.payment_worker import payment_worker_node
from app.agents.reviewer_agent import reviewer_agent_node
from app.agents.conflict_resolver_agent import conflict_resolver_node
from langchain_core.messages import AIMessage
from functools import partial
import logging

logger = logging.getLogger(__name__)


def dispatcher_node(state: AgentState):
    """Routes tasks to workers based on dependencies. One worker per type per turn."""
    plan = state.get("plan", [])
    task_statuses = state.get("task_statuses", {})
    
    next_workers = []
    updated_statuses = task_statuses.copy()
    active_worker_types = set()
    
    for step in plan:
        step_id = step["id"]
        status = task_statuses.get(step_id, "pending")
        worker_type = step["worker"]
        
        if status == "failed":
            return {"error": f"Task {step_id} Failed after retries."}

        if status in ["pending", "reviewing"]:
            deps = step.get("dependencies", [])
            deps_met = all(updated_statuses.get(d) == "approved" for d in deps)
            
            if deps_met and worker_type not in active_worker_types:
                updated_statuses[step_id] = "in_progress"
                next_workers.append(worker_type)
                active_worker_types.add(worker_type)
                logger.info(f"ACTIVATING Task {step_id} for {worker_type}")
    
    return {"task_statuses": updated_statuses, "next_workers": next_workers}


def dispatcher_edge(state: AgentState):
    """Edge function: routes to workers or end states."""
    if state.get("error"):
        return "end_fail"
        
    next_workers = state.get("next_workers", [])
    task_statuses = state.get("task_statuses", {})
    plan = state.get("plan", [])
    
    if not next_workers:
        all_complete = all(task_statuses.get(s["id"]) in ["approved", "failed"] for s in plan)
        # Gap 3 Fix: Route to conflict_resolver before output_supervisor
        return "conflict_resolver" if all_complete else "end_fail"
            
    return next_workers


def supervisor_router(state: AgentState):
    """Edge function: routes based on supervisor verdict."""
    verdict = state.get("supervisor_verdict", "ignore")
    if verdict == "safe":
        return "planner"
    elif verdict == "cached":
        # Cache hit - skip directly to output supervisor for logging
        return "output_supervisor"
    elif verdict == "block":
        return "end_block"
    return "end_ignore"


def output_supervisor_router(state: AgentState):
    """Edge function: routes based on output supervisor verdict."""
    if state.get("supervisor_output_verdict", "safe") == "block":
        return "end_block"
    return END


# --- Graph Construction ---
workflow = StateGraph(AgentState)

# Core nodes
workflow.add_node("supervisor", supervisor_agent_node)
workflow.add_node("planner", planner_agent_node)
workflow.add_node("dispatcher", dispatcher_node)

# Workers
workflow.add_node("sales_worker", sales_worker_node)
workflow.add_node("admin_worker", admin_worker_node)
workflow.add_node("payment_worker", payment_worker_node)
workflow.add_node("email_alert", admin_email_alert_node)

# Scoped reviewers
workflow.add_node("sales_reviewer", partial(reviewer_agent_node, worker_scope="sales_worker"))
workflow.add_node("admin_reviewer", partial(reviewer_agent_node, worker_scope="admin_worker"))
workflow.add_node("payment_reviewer", partial(reviewer_agent_node, worker_scope="payment_worker"))

# Output supervisor
workflow.add_node("output_supervisor", output_supervisor_node)

# Entry point
workflow.set_entry_point("supervisor")

# Supervisor edges (added "cached" → output_supervisor)
workflow.add_conditional_edges(
    "supervisor",
    supervisor_router,
    {
        "planner": "planner", 
        "output_supervisor": "output_supervisor",  # Cache hit path
        "end_block": END, 
        "end_ignore": END
    }
)

# Planner -> Dispatcher
workflow.add_edge("planner", "dispatcher")

# Dispatcher fan-out to workers
workflow.add_conditional_edges(
    "dispatcher",
    dispatcher_edge,
    {
        "sales_worker": "sales_worker",
        "admin_worker": "admin_worker",
        "payment_worker": "payment_worker",
        "conflict_resolver": "conflict_resolver",
        "end_fail": "email_alert"
    }
)

# Worker -> Reviewer edges
workflow.add_edge("sales_worker", "sales_reviewer")
workflow.add_edge("admin_worker", "admin_reviewer")
workflow.add_edge("payment_worker", "payment_reviewer")

# Reviewer -> Dispatcher loop
workflow.add_edge("sales_reviewer", "dispatcher")
workflow.add_edge("admin_reviewer", "dispatcher")
workflow.add_edge("payment_reviewer", "dispatcher")

# Conflict Resolution (Gap 3 Fix)
workflow.add_node("conflict_resolver", conflict_resolver_node)
workflow.add_edge("conflict_resolver", "output_supervisor")

# End nodes
workflow.add_edge("email_alert", END)
workflow.add_conditional_edges(
    "output_supervisor",
    output_supervisor_router,
    {"end_block": END, END: END}
)

app = workflow.compile()
