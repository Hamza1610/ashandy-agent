from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from app.models.agent_states import AgentState
from app.agents.router_agent import router_agent_node
from app.agents.safety_agent import safety_agent_node
from app.agents.visual_search_agent import visual_search_agent_node
from app.agents.sales_consultant_agent import sales_consultant_agent_node
from app.agents.payment_order_agent import payment_order_agent_node
from app.agents.admin_agent import admin_agent_node
import logging

logger = logging.getLogger(__name__)

# Conditional Edges
def route_after_router(state: AgentState):
    if state.get("is_admin"):
        return "admin"
    return "safety"

def route_after_safety(state: AgentState):
    if state.get("error"):
        return END # Stop if unsafe or error
    return "query_router"

def route_query_type(state: AgentState):
    q_type = state.get("query_type")
    if q_type == "image":
        return "visual"
    return "sales" # Default to sales for text

def route_after_sales(state: AgentState):
    if state.get("order_intent"):
        return "payment"
    return END

# Graph Construction
workflow = StateGraph(AgentState)

# Nodes
workflow.add_node("router", router_agent_node)
workflow.add_node("safety", safety_agent_node)
workflow.add_node("admin", admin_agent_node)
workflow.add_node("visual", visual_search_agent_node)
workflow.add_node("sales", sales_consultant_agent_node)
workflow.add_node("payment", payment_order_agent_node)
# Note: In a full implementation, we might have a strict 'response' node to format final output for Meta API.
# Here we assume the agents return the final message in 'messages' which the API layer will pick up.

# Edges
workflow.add_edge(START, "router")
workflow.add_conditional_edges("router", route_after_router)
workflow.add_conditional_edges("safety", route_after_safety, {"END": END, "query_router": "query_router"}) # map simplified strings if needed, but here simple return works with logic

# We need a dummy node or logic for "query_router" or just handle it in the edge function above mapping to node names directly.
# Let's adjust route_after_safety to return node names directly.
def route_after_safety_direct(state: AgentState):
    if state.get("error"):
        return END
    
    # Determine where to go next based on query type
    q_type = state.get("query_type")
    if q_type == "image":
        return "visual"
    return "sales"

workflow.add_conditional_edges("safety", route_after_safety_direct)

workflow.add_edge("visual", "sales") # Visual search results feed into sales consultant for context
workflow.add_conditional_edges("sales", route_after_sales)
workflow.add_edge("payment", END)
workflow.add_edge("admin", END)

# Compile
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)

logger.info("LangGraph workflow compiled.")
