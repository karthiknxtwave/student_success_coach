from agents.state import AgentState
from knowledge.chroma_client import retrieve


def fetch_knowledge(state: AgentState) -> AgentState:
    """
    Node 2b (conditional): Retrieve relevant course knowledge from ChromaDB.
    Runs when route is 'knowledge_base' or 'both'.
    No LLM is used — pure embedding similarity search.
    """
    query = state.get("user_message", "")
    knowledge_context = retrieve(query)  # Returns str or None if collection empty
    print("data retrieved from vectordb")
    return {**state, "knowledge_context": knowledge_context}