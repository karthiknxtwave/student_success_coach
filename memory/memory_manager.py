import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from memory.mem0_client import add_memory, get_facts, get_summaries
from signals.signal_detector import detect_signals
from sheets.client import build_student_context, append_signals

# ---------------------------------------------------------------------------
# SUMMARY PROMPT — edit to change what gets captured in session summaries
# ---------------------------------------------------------------------------
_SUMMARY_PROMPT = """You are summarizing a coaching session for a Student Success Coach application.

Given the conversation below, write a concise session summary that captures:
- What academic topics or problems were discussed
- Any important academic issues identified (low scores, attendance, upcoming exams)
- Decisions made during the session
- Action plans or commitments the student agreed to

Keep it brief — 4 to 6 bullet points maximum.
Do NOT include small talk, greetings, or irrelevant exchanges.

Format:
- <bullet point>
- <bullet point>
...
"""

# ---------------------------------------------------------------------------
# FACT EXTRACTION PROMPT — edit to change what gets stored as long-term memory
# ---------------------------------------------------------------------------
_FACT_EXTRACTION_PROMPT = """You are extracting long-term memory facts from a student coaching session.

Given the conversation below, extract ONLY facts that would still be useful 3 months from now.

Good facts to extract:
- Learning preferences (e.g. prefers video-based learning, likes structured plans)
- Academic strengths and weaknesses (e.g. struggles with Machine Learning, strong in SQL)
- Motivation and stress patterns (e.g. experiences exam anxiety, motivated by deadlines)
- Study habits (e.g. studies best in the morning, procrastinates on theory)
- Goals and commitments (e.g. wants attendance above 85%, committed to daily practice)

Bad facts — DO NOT extract these:
- Greetings or small talk ("said hello", "thanked the coach")
- One-off questions with no lasting relevance
- Session-specific details already captured in the summary

Return ONLY a JSON array of strings. No explanation. No markdown. No preamble.
Example output:
["Struggles with Machine Learning concepts.", "Prefers structured weekly study plans.", "Experiences anxiety before exams."]

If there are no meaningful long-term facts, return an empty array: []
"""


def _format_chat_for_llm(chat_history: list[dict]) -> str:
    """Convert chat history list into a readable string for the LLM."""
    print("collecting and formatting chat")
    lines = []
    for turn in chat_history:
        role = "Student" if turn["role"] == "user" else "Coach"
        lines.append(f"{role}: {turn['content']}")
    print("chat format done")
    return "\n".join(lines)


def _get_llm():
    return ChatOpenAI(
        model=st.secrets["app"]["OPENAI_MODEL"],
        temperature=0,
        api_key=st.secrets["app"]["OPENAI_API_KEY"],
    )


def load_memories(student_id: str) -> dict:
    """
    Called at session start when a student is selected.
    Retrieves long-term facts and recent session summaries from Mem0.
    """
    facts = get_facts(student_id)
    summaries = get_summaries(student_id)

    memories_str = "\n".join(f"- {f}" for f in facts) if facts else None
    summaries_str = "\n".join(f"- {s}" for s in summaries) if summaries else None
    print("memories loaded")
    return {
        "memories": memories_str,
        "recent_summaries": summaries_str,
    }


def save_session(student_id: str, chat_history: list[dict]) -> None:
    """
    Called at session end when the student clicks End Session.
    1. Generates a session summary and stores it in Mem0.
    2. Extracts long-term facts and stores each one in Mem0.
    3. Detects signals and stores them in Google Sheets.
    """
    llm = _get_llm()
    conversation_text = _format_chat_for_llm(chat_history)

    # --- Step 1: Generate and store session summary ---
    summary_messages = [
        SystemMessage(content=_SUMMARY_PROMPT),
        HumanMessage(content=conversation_text),
    ]
    summary_result = llm.invoke(summary_messages)
    summary_text = summary_result.content.strip()

    if summary_text:
        add_memory(
            content=summary_text,
            student_id=student_id,
            memory_type="session_summary",
        )

    # --- Step 2: Extract and store long-term facts ---
    fact_messages = [
        SystemMessage(content=_FACT_EXTRACTION_PROMPT),
        HumanMessage(content=conversation_text),
    ]
    fact_result = llm.invoke(fact_messages)
    raw = fact_result.content.strip()

    try:
        import json
        clean = raw.replace("```json", "").replace("```", "").strip()
        facts = json.loads(clean)
        if isinstance(facts, list):
            for fact in facts:
                if isinstance(fact, str) and fact.strip():
                    add_memory(
                        content=fact.strip(),
                        student_id=student_id,
                        memory_type="fact",
                    )
        print("session saved")
    except (json.JSONDecodeError, ValueError):
        print("failed to save session")
        pass

    # --- Step 3: Detect and store signals ---
    try:
        student_context = build_student_context(student_id)
        signals = detect_signals(conversation_text, student_context)
        append_signals(signals, student_id)
        print(f"[signals] Detection complete. {len(signals)} signal(s) found.")
    except Exception as e:
        print(f"[signals] Detection failed: {e}")