# signals/brief_generator.py

import json
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

_BRIEF_PROMPT = """You are a Student Success Coach assistant preparing a pre-meeting brief.
You will be given a student's current academic data, open risk signals, long-term memory
facts about the student, and recent session summaries.

Generate a brief that covers:
1. Current academic situation (attendance, scores, upcoming exams)
2. What has changed or progressed since the last session (infer naturally from summaries vs current data)
3. Open concerns (from signals and memory)
4. Specific focus for today's session

Rules:
- 4–8 sentences maximum. The coach must be able to read this in under 30 seconds.
- After the brief, generate 1–3 personalized conversation-starter questions.
- Questions must be grounded in the student's specific data, memories, or signals — never generic.
- Return ONLY a JSON object. No markdown. No preamble.

Output format:
{
  "brief": "<4-8 sentence brief>",
  "questions": ["<question 1>", "<question 2>", "<question 3>"]
}
"""

def _get_llm():
    return ChatOpenAI(
        model=st.secrets["app"]["OPENAI_MODEL"],
        temperature=0.3,
        api_key=st.secrets["app"]["OPENAI_API_KEY"],
    )

def _format_signals(signals: list[dict]) -> str:
    if not signals:
        return "None."
    lines = []
    for s in signals:
        lines.append(f"- {s['signal_type']} ({s['severity']}, {s['urgency']}): {s['reason']}")
    return "\n".join(lines)

def _format_academic_data(ctx: dict) -> str:
    # Reuse same formatting logic as signal_detector.py
    lines = []
    att = ctx.get("latest_attendance")
    lines.append(f"Attendance: {att['attendance_pct']}% (week of {att['week_of']})" if att else "Attendance: No data.")
    scores = ctx.get("recent_scores", [])
    if scores:
        lines.append("Recent Scores:")
        for s in scores:
            lines.append(f"  - {s['subject']}: {s['score']}/{s['max_score']} on {s['date']}")
    else:
        lines.append("Scores: No data.")
    exams = ctx.get("upcoming_exams", [])
    if exams:
        lines.append("Upcoming Exams:")
        for e in exams:
            lines.append(f"  - {e['subject']} on {e['exam_date']} ({e['days_remaining']} day(s) away)")
    else:
        lines.append("Upcoming Exams: None.")
    return "\n".join(lines)

def generate_brief(
    student_id: str,
    student_context: dict,
    open_signals: list[dict],
    facts: list[str],
    summaries: list[str],
) -> dict:
    """
    Generate a pre-meeting brief for one student.
    Returns {"brief": str, "questions": list[str]}.
    All data is passed in — no fetching here.
    """
    academic_text  = _format_academic_data(student_context)
    signals_text   = _format_signals(open_signals)
    facts_text     = "\n".join(f"- {f}" for f in facts) if facts else "None."
    summaries_text = "\n".join(f"- {s}" for s in summaries) if summaries else "None."

    user_content = f"""=== STUDENT: {student_context.get('name')} | {student_context.get('program')} | Cohort {student_context.get('cohort')} ===

=== ACADEMIC DATA ===
{academic_text}

=== OPEN SIGNALS ===
{signals_text}

=== LONG-TERM MEMORY (facts) ===
{facts_text}

=== RECENT SESSION SUMMARIES (last {len(summaries)}) ===
{summaries_text}
"""

    llm = _get_llm()
    result = llm.invoke([
        SystemMessage(content=_BRIEF_PROMPT),
        HumanMessage(content=user_content),
    ])

    raw = result.content.strip()
    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        if isinstance(parsed, dict) and "brief" in parsed and "questions" in parsed:
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: return raw text as brief with no questions
    return {"brief": raw, "questions": []}