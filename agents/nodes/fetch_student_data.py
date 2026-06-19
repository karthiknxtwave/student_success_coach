from agents.state import AgentState
from sheets.client import build_student_context


def fetch_student_data(state: AgentState) -> AgentState:
    """
    Node 2a (conditional): Fetch student academic data from Google Sheets.
    Runs when route is 'student_data' or 'both'.
    """
    student_id = state.get("student_id")

    if not student_id:
        return {**state, "student_context": None}

    context = build_student_context(student_id)
    return {**state, "student_context": context}