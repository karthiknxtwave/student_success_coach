from agents.state import AgentState
from sheets.client import build_student_context


def fetch_student_data(state: AgentState) -> AgentState:
    """
    Node 2 (conditional): Fetch student academic data from Google Sheets.
    Only runs when needs_data is True.
    """
    student_id = state.get("student_id")

    if not student_id:
        # No student selected — skip silently
        return {**state, "student_context": None}

    context = build_student_context(student_id)
    return {**state, "student_context": context}