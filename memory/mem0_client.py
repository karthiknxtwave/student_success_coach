import streamlit as st
from mem0 import MemoryClient

# ---------------------------------------------------------------------------
# CONFIG — edit these to change retrieval limits
# ---------------------------------------------------------------------------
MAX_FACTS = 5          # Max long-term facts retrieved per session
MAX_SUMMARIES = 3      # Max recent session summaries retrieved per session
# ---------------------------------------------------------------------------


def _get_client() -> MemoryClient:
    """Return a Mem0 client using credentials from st.secrets."""
    return MemoryClient(api_key=st.secrets["mem0"]["MEM0_API_KEY"])


def add_memory(content: str, student_id: str, memory_type: str) -> None:
    """
    Store a single memory in Mem0.

    Args:
        content:      The memory text to store.
        student_id:   Used as the Mem0 user identifier.
        memory_type:  "fact" or "session_summary"
    """
    print("adding to memory")
    client = _get_client()
    client.add(
        messages=[{"role": "user", "content": content}],
        user_id=student_id,
        metadata={"type": memory_type},
    )


def get_facts(student_id: str) -> list[str]:
    client = _get_client()
    results = client.search(
        query="learning preferences strengths weaknesses habits goals",
        filters={"user_id": student_id},
        limit=20,
    )
    facts = [
        r["memory"] for r in results.get("results", [])
        if r.get("metadata", {}).get("type") == "fact"
    ]
    return facts[:MAX_FACTS]


def get_summaries(student_id: str) -> list[str]:
    client = _get_client()
    results = client.search(
        query="session summary discussion decisions action plan",
        filters={"user_id": student_id},
        limit=20,
    )
    summaries = [
        r["memory"] for r in results.get("results", [])
        if r.get("metadata", {}).get("type") == "session_summary"
    ]
    return summaries[:MAX_SUMMARIES]