import json


COACH_PERSONA = """You are a warm, encouraging Student Success Coach at an educational institution.
Your role is to help students improve their academic performance and stay on track.
Be specific, actionable, and supportive. Never be generic or vague.
Always prioritize urgent concerns (failing grades, low attendance, imminent exams) first.
You strictly only answer queries related to student's academic performance or any of their enrolled course (Data science / Full Stack Development)
Any unrelated query must be rejected politely."""


def build_general_prompt(student_name: str | None = None) -> str:
    """System prompt for general (non-data) queries."""
    name_line = f"You are currently speaking with {student_name}." if student_name else ""
    return f"""{COACH_PERSONA}
{name_line}
Answer the student's question helpfully. If they ask about their grades, attendance,
or exams, let them know you can look that up if they'd like."""


def build_data_prompt(student_context: dict) -> str:
    """System prompt enriched with the student's academic data."""
    ctx = student_context

    # --- Format scores ---
    if ctx.get("recent_scores"):
        scores_text = "\n".join(
            f"  - {s['subject']}: {s['score']}/{s['max_score']} on {s['date']}"
            for s in ctx["recent_scores"]
        )
    else:
        scores_text = "  No exam records available."

    # --- Format attendance ---
    att = ctx.get("latest_attendance")
    if att:
        pct = att.get("attendance_pct", 0)
        attendance_text = f"  Latest week ({att.get('week_of')}): {pct}%"
    else:
        attendance_text = "  No attendance records available."

    # --- Format upcoming exams ---
    if ctx.get("upcoming_exams"):
        exams_text = "\n".join(
            f"  - {e['subject']} ({e.get('exam_type', 'Exam')}) on {e['exam_date']} "
            f"— {e['days_remaining']} day(s) away"
            + ("HIGH PRIORITY" if e["days_remaining"] <= 3 else
               "UPCOMING" if e["days_remaining"] <= 7 else "")
            for e in ctx["upcoming_exams"]
        )
    else:
        exams_text = "No upcoming exams scheduled."

    return f"""{COACH_PERSONA}

You are speaking with {ctx.get('name', 'the student')} 
(Program: {ctx.get('program', 'N/A')}, Cohort: {ctx.get('cohort', 'N/A')}).

=== STUDENT ACADEMIC DATA ===

Recent Exam Scores:
{scores_text}

Attendance:
{attendance_text}

Upcoming Exams:
{exams_text}

=== INSTRUCTIONS ===
- Use the data above to personalise your response.
- Mention weak subjects (low scores) and what to do about them.
- Flag low attendance if below 75%.
- Highlight exams within 7 days, with high urgency for exams within 3 days.
- Be specific — reference actual subjects, scores, and dates from the data.
- Do not invent any data not listed above.
"""