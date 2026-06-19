import json
import streamlit as st
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

# ---------------------------------------------------------------------------
# ALLOWED VALUES — do not change these without updating the sheet schema
# ---------------------------------------------------------------------------
ALLOWED_SIGNAL_TYPES = {
    "attendance_risk",
    "performance_risk",
    "exam_risk",
    "motivation_risk",
    "stress_risk",
    "engagement_risk",
    "dropout_risk",
}
ALLOWED_SEVERITIES = {"low", "medium", "high"}
ALLOWED_URGENCIES  = {"today", "tomorrow", "this_week"}

# ---------------------------------------------------------------------------
# SIGNAL DETECTION PROMPT — edit to tune what signals get raised
# ---------------------------------------------------------------------------
_SIGNAL_PROMPT = """You are a signal detector for a Student Success Coach application.
Your job is to identify situations that may require intervention from a human coach.

You will be given:
1. A coaching session conversation
2. The student's current academic data (attendance, scores, upcoming exams)

Analyze both and raise signals for any concerning situation.
Raise a signal even if the student never explicitly mentioned the issue.
Example: If attendance is 52%, raise attendance_risk regardless of what was discussed.

Allowed signal_type values (use ONLY these):
- attendance_risk
- performance_risk
- exam_risk
- motivation_risk
- stress_risk
- engagement_risk
- dropout_risk

Allowed severity values (use ONLY these):
- low
- medium
- high

Allowed urgency values (use ONLY these):
- today
- tomorrow
- this_week

Severity guidelines:
- attendance_risk: high if <65%, medium if 65-75%, low if 75-85%
- performance_risk: high if any score <50%, medium if 50-65%, low if 65-75%
- exam_risk: high if exam within 3 days and score in that subject is low, medium if within 7 days
- motivation_risk / stress_risk / engagement_risk: infer from conversation tone and content
- dropout_risk: high if attendance_risk + performance_risk + motivation_risk all present together

Urgency guidelines:
- today: requires immediate attention
- tomorrow: should be addressed within 24 hours
- this_week: should be addressed this week

Return ONLY a JSON array of signal objects. No explanation. No markdown. No preamble.
Each object must have exactly these keys: signal_type, severity, urgency, reason

Example output:
[
  {
    "signal_type": "attendance_risk",
    "severity": "high",
    "urgency": "today",
    "reason": "Student attendance is at 52%, well below the 75% threshold."
  },
  {
    "signal_type": "performance_risk",
    "severity": "medium",
    "urgency": "this_week",
    "reason": "Student scored 58/100 in Machine Learning, indicating weak understanding."
  }
]

If no signals are warranted, return an empty array: []
"""
# ---------------------------------------------------------------------------


def _get_llm():
    return ChatOpenAI(
        model=st.secrets["app"]["OPENAI_MODEL"],
        temperature=0,
        api_key=st.secrets["app"]["OPENAI_API_KEY"],
    )


def _format_academic_data(student_context: dict) -> str:
    """Format student academic data into a readable string for the LLM."""
    if not student_context:
        return "No academic data available."

    lines = []

    # Attendance
    att = student_context.get("latest_attendance")
    if att:
        lines.append(f"Attendance: {att.get('attendance_pct')}% (week of {att.get('week_of')})")
    else:
        lines.append("Attendance: No data available.")

    # Scores
    scores = student_context.get("recent_scores", [])
    if scores:
        lines.append("Recent Scores:")
        for s in scores:
            lines.append(f"  - {s['subject']}: {s['score']}/{s['max_score']} on {s['date']}")
    else:
        lines.append("Scores: No data available.")

    # Upcoming exams
    exams = student_context.get("upcoming_exams", [])
    if exams:
        lines.append("Upcoming Exams:")
        for e in exams:
            lines.append(
                f"  - {e['subject']} ({e.get('exam_type', 'Exam')}) "
                f"on {e['exam_date']} — {e['days_remaining']} day(s) away"
            )
    else:
        lines.append("Upcoming Exams: None.")

    return "\n".join(lines)


def _validate_signals(raw_signals: list) -> list[dict]:
    """Keep only signals with valid types, severities, and urgencies."""
    validated = []
    for s in raw_signals:
        if not isinstance(s, dict):
            continue
        if s.get("signal_type") not in ALLOWED_SIGNAL_TYPES:
            continue
        if s.get("severity") not in ALLOWED_SEVERITIES:
            continue
        if s.get("urgency") not in ALLOWED_URGENCIES:
            continue
        if not s.get("reason", "").strip():
            continue
        validated.append({
            "signal_type": s["signal_type"],
            "severity":    s["severity"],
            "urgency":     s["urgency"],
            "reason":      s["reason"].strip(),
        })
    return validated


def detect_signals(
    conversation_text: str,
    student_context: dict,
) -> list[dict]:
    """
    Analyze the session conversation and academic data.
    Returns a validated list of signal dicts.

    Each dict has: signal_type, severity, urgency, reason
    """
    academic_text = _format_academic_data(student_context)

    user_content = f"""=== STUDENT ACADEMIC DATA ===
{academic_text}

=== SESSION CONVERSATION ===
{conversation_text}
"""

    llm = _get_llm()
    messages = [
        SystemMessage(content=_SIGNAL_PROMPT),
        HumanMessage(content=user_content),
    ]

    result = llm.invoke(messages)
    raw = result.content.strip()

    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(clean)
        if isinstance(parsed, list):
            return _validate_signals(parsed)
    except (json.JSONDecodeError, ValueError):
        pass

    return []