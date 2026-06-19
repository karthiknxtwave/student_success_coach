from typing import Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):
    student_id: str
    user_message: str
    chat_history: list[dict]
    route: str                        # "general" | "student_data" | "knowledge_base" | "both"
    student_context: Optional[dict]
    knowledge_context: Optional[str]  # Retrieved RAG chunks as a single string
    memories: Optional[str]           # Long-term facts retrieved from Mem0
    recent_summaries: Optional[str]   # Last 3 session summaries retrieved from Mem0
    response: str