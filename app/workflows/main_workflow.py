from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.models.agent_states import AgentState
from app.agents.supervisor_agent import supervisor_agent_node
from app.agents.planner_agent import planner_agent_node
from app.agents.sales_worker import sales_worker_node
from app.agents.admin_worker import admin_worker_node
from app.agents.payment_worker import payment_worker_node
from app.services.meta_service import meta_service
import logging

logger = logging.getLogger(__name__)

# -----------------------------
# Nodes
# -----------------------------

async def supervisor_gate(state: AgentState):
    """Entry point: Supervisor Check."""
    return await supervisor_agent_node(state)

async def planner_brain(state: AgentState):
    """The Brain: Decomposes tasks."""
    return await planner_agent_node(state)

async def dispatcher_node(state: AgentState):
    """
    Dispatcher: Routes to next worker or response based on Plan index.
    Does NOT call LLM. Just acts as a traffic circle.
    """
    return {}

async def next_step_node(state: AgentState):
    """
    Increments the step index to move to the next task in the plan.
    """
    idx = state.get("current_step_index", 0)
    return {"current_step_index": idx + 1}

# --- Workers ---
async def sales_worker(state: AgentState):
    return await sales_worker_node(state)

async def admin_worker(state: AgentState):
    return await admin_worker_node(state)

async def payment_worker(state: AgentState):
    return await payment_worker_node(state)

# --- Response / Output ---
async def response_manager(state: AgentState):
    """
    Consolidates results and sends final response to user.
    """
    user_id = state.get("user_id")
    platform = state.get("platform")
    
    # We look at the last "worker_result" or extract from state messages
    result_text = state.get("worker_result", "")
    
    if not result_text:
        # Fallback to last message content
        msgs = state.get("messages", [])
        if msgs:
            result_text = msgs[-1].content
            
    if not result_text:
        return {}

    # Send to Platform
    if platform == "whatsapp":
        await meta_service.send_whatsapp_text(user_id, result_text)
    elif platform == "instagram":
        await meta_service.send_instagram_text(user_id, result_text)
        
    return {}


# -----------------------------
# Routing Logic (Edges)
# -----------------------------

def route_supervisor(state: AgentState):
    verdict = state.get("supervisor_verdict", "safe")
    
    if verdict == "block":
        # Blocked but with a message? Send it.
        return "response_manager"
        
    if verdict == "ignore":
        # Silent ignore (e.g. spam)
        return END
        
    if verdict == "handoff":
        return "admin_worker" # Handover is an admin task
    return "planner"

def route_dispatcher(state: AgentState):
    """
    Dispatcher decides: Do we have a pending task?
    """
    plan = state.get("plan", [])
    idx = state.get("current_step_index", 0)
    
    if idx < len(plan):
        # We have a task. Identify worker.
        current_step = plan[idx]
        worker_name = current_step.get("worker", "sales_worker")
        
        if worker_name == "admin_worker":
            return "admin_worker"
        elif worker_name == "payment_worker":
            return "payment_worker"
        else:
            return "sales_worker"
            
    # No more tasks? we are done.
    return "response_manager"

# -----------------------------
# Graph Build
# -----------------------------
workflow = StateGraph(AgentState)

# Nodes
workflow.add_node("supervisor", supervisor_gate)
workflow.add_node("planner", planner_brain)
workflow.add_node("dispatcher", dispatcher_node)

workflow.add_node("sales_worker", sales_worker)
workflow.add_node("admin_worker", admin_worker)
workflow.add_node("payment_worker", payment_worker)

workflow.add_node("next_step", next_step_node)
workflow.add_node("response_manager", response_manager)

# Edges
workflow.add_edge(START, "supervisor")
workflow.add_conditional_edges("supervisor", route_supervisor, {
    "planner": "planner",
    "admin_worker": "admin_worker", 
    "response_manager": "response_manager",
    END: END
})

workflow.add_edge("planner", "dispatcher") # Planner done -> Dispatcher

workflow.add_conditional_edges("dispatcher", route_dispatcher, {
    "sales_worker": "sales_worker",
    "admin_worker": "admin_worker",
    "payment_worker": "payment_worker",
    "response_manager": "response_manager"
})

workflow.add_edge("sales_worker", "next_step")
workflow.add_edge("admin_worker", "next_step")
workflow.add_edge("payment_worker", "next_step")

workflow.add_edge("next_step", "dispatcher") # Loop back to Dispatcher (NOT Planner)

workflow.add_edge("response_manager", END)

# Compile
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

logger.info("Supervisor-Planner-Worker Graph Compiled.")
