from langgraph.graph import StateGraph, END
from agents.state import AgentState
from agents.nodes.router import route_message
from agents.nodes.fetch_data import fetch_student_data
from agents.nodes.generate import generate_response


def _should_fetch_data(state: AgentState) -> str:
    """Conditional edge: route to fetch_data or skip straight to generate."""
    if state.get("needs_data"):
        return "fetch_data"
    return "generate"


def build_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # Register nodes
    graph.add_node("router", route_message)
    graph.add_node("fetch_data", fetch_student_data)
    graph.add_node("generate", generate_response)

    # Entry point
    graph.set_entry_point("router")

    # Conditional edge after router
    graph.add_conditional_edges(
        "router",
        _should_fetch_data,
        {
            "fetch_data": "fetch_data",
            "generate": "generate",
        },
    )

    # fetch_data always leads to generate
    graph.add_edge("fetch_data", "generate")

    # generate is the final node
    graph.add_edge("generate", END)

    return graph.compile()


# Singleton — compiled once and reused
agent_graph = build_graph()