from langgraph.graph import StateGraph, END
from app.state.agent_state import AgentState
from app.agents.supervisor_agent import supervisor_agent_node
from app.agents.planner_agent import planner_agent_node
from app.agents.sales_worker import sales_worker_node
from app.agents.admin_worker import admin_worker_node
from app.agents.payment_worker import payment_worker_node
from langchain_core.messages import AIMessage
import logging

logger = logging.getLogger(__name__)

# --- Router Functions ---

def supervisor_router(state: AgentState):
    verdict = state.get("supervisor_verdict", "ignore")
    if verdict == "safe":
        return "planner"
    elif verdict == "block":
        return "end_block" # We might want to send a message before ending
    else:
        return "end_ignore"

def planner_router(state: AgentState):
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    
    if idx >= len(plan):
        return "end_done"
        
    step = plan[idx]
    worker_name = step.get("worker", "sales_worker")
    
    return worker_name

# --- Helper Nodes ---

async def next_step_node(state: AgentState):
    """Increments the step index to move to the next task."""
    idx = state.get("current_step_index", 0)
    return {"current_step_index": idx + 1}

async def end_status_node(state: AgentState):
    """Optional cleanup or final logging."""
    return {}

# --- Graph Construction ---

workflow = StateGraph(AgentState)

# Add Nodes
workflow.add_node("supervisor", supervisor_agent_node)
workflow.add_node("planner", planner_agent_node)
workflow.add_node("sales_worker", sales_worker_node)
workflow.add_node("admin_worker", admin_worker_node)
workflow.add_node("payment_worker", payment_worker_node)
workflow.add_node("next_step", next_step_node)

# Set Entry Point
workflow.set_entry_point("supervisor")

# Supervisor Edges
workflow.add_conditional_edges(
    "supervisor",
    supervisor_router,
    {
        "planner": "planner",
        "end_block": END,
        "end_ignore": END
    }
)

# Planner Router Logic (Dispatcher)
# This router is called after 'planner' (initial) and after 'next_step' (loop)
workflow.add_conditional_edges(
    "planner",
    planner_router,
    {
        "sales_worker": "sales_worker",
        "admin_worker": "admin_worker",
        "payment_worker": "payment_worker",
        "end_done": END
    }
)

workflow.add_conditional_edges(
    "next_step",
    planner_router,
    {
        "sales_worker": "sales_worker",
        "admin_worker": "admin_worker",
        "payment_worker": "payment_worker",
        "end_done": END
    }
)

# Worker Edges -> Next Step
workflow.add_edge("sales_worker", "next_step")
workflow.add_edge("admin_worker", "next_step")
workflow.add_edge("payment_worker", "next_step")

# Compile
app = workflow.compile()
