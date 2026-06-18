from typing import Optional
from typing_extensions import TypedDict


class AgentState(TypedDict):
    student_id: str
    user_message: str
    chat_history: list[dict]
    needs_data: bool
    student_context: Optional[dict]
    response: str