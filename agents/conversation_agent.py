from agents.graph import agent_graph


class ConversationAgent:
    """
    Thin wrapper around the LangGraph agent.
    Keeps the same .chat() interface that main.py already uses.
    """

    def chat(
        self,
        message: str,
        student_id: str = "",
        chat_history: list[dict] = None,
        memories: str | None = None,
        recent_summaries: str | None = None,
    ) -> str:
        """
        Run the agent graph and return the response string.

        Args:
            message:          The student's latest message.
            student_id:       The selected student's ID.
            chat_history:     List of {"role": ..., "content": ...} dicts.
            memories:         Long-term facts loaded from Mem0 at session start.
            recent_summaries: Recent session summaries loaded from Mem0 at session start.
        """
        if chat_history is None:
            chat_history = []

        initial_state = {
            "student_id": student_id,
            "user_message": message,
            "chat_history": chat_history,
            "route": "general",
            "student_context": None,
            "knowledge_context": None,
            "memories": memories,
            "recent_summaries": recent_summaries,
            "response": "",
        }

        final_state = agent_graph.invoke(initial_state)
        return final_state["response"]