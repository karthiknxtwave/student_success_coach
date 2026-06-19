from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.nodes.router import route_message
from agents.nodes.fetch_student_data import fetch_student_data
from agents.nodes.fetch_knowledge import fetch_knowledge
from agents.nodes.generate import generate_response


def _route_after_router(state: AgentState) -> str:
    """
    Conditional edge after the router node.
    Returns the next node name based on state['route'].
    """
    route = state.get("route", "general")

    if route == "student_data":
        return "fetch_student_data"
    elif route == "knowledge_base":
        return "fetch_knowledge"
    elif route == "both":
        return "fetch_student_data"   # both: student_data first, then knowledge
    else:
        return "generate"             # general


def _route_after_student_data(state: AgentState) -> str:
    """
    Conditional edge after fetch_student_data.
    If route is 'both', continue to fetch_knowledge; otherwise go to generate.
    """
    if state.get("route") == "both":
        return "fetch_knowledge"
    return "generate"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("router", route_message)
    graph.add_node("fetch_student_data", fetch_student_data)
    graph.add_node("fetch_knowledge", fetch_knowledge)
    graph.add_node("generate", generate_response)

    # Entry point
    graph.set_entry_point("router")

    # router → one of: fetch_student_data | fetch_knowledge | generate
    graph.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "fetch_student_data": "fetch_student_data",
            "fetch_knowledge": "fetch_knowledge",
            "generate": "generate",
        },
    )

    # fetch_student_data → fetch_knowledge (if both) or generate
    graph.add_conditional_edges(
        "fetch_student_data",
        _route_after_student_data,
        {
            "fetch_knowledge": "fetch_knowledge",
            "generate": "generate",
        },
    )

    # fetch_knowledge always leads to generate
    graph.add_edge("fetch_knowledge", "generate")

    # generate is the final node
    graph.add_edge("generate", END)

    return graph.compile()


# Singleton — compiled once and reused
agent_graph = build_graph()