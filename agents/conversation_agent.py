from agents.graph import agent_graph


class ConversationAgent:
    """
    Thin wrapper around the LangGraph agent.
    Keeps the same .chat() interface that main.py already uses,
    but now accepts student_id and chat_history for personalisation.
    """

    def chat(
        self,
        message: str,
        student_id: str = "",
        chat_history: list[dict] = None,
    ) -> str:
        """
        Run the agent graph and return the response string.

        Args:
            message:       The student's latest message.
            student_id:    The selected student's ID (empty string if none selected).
            chat_history:  List of {"role": "user"/"assistant", "content": "..."} dicts.
        """
        if chat_history is None:
            chat_history = []

        initial_state = {
            "student_id": student_id,
            "user_message": message,
            "chat_history": chat_history,
            "needs_data": False,
            "student_context": None,
            "response": "",
        }

        final_state = agent_graph.invoke(initial_state)
        return final_state["response"]