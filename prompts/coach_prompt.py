# =============================================================================
# coach_prompt.py
#
# All prompt templates live here. Edit the clearly marked sections below
# to tune the coach's behaviour without touching any other file.
# =============================================================================


# -----------------------------------------------------------------------------
# COACH PERSONA — shared across all prompts
# Edit this to change the coach's tone and ground rules.
# -----------------------------------------------------------------------------
COACH_PERSONA = """You are a warm, encouraging Student Success Coach at an educational institution.
Your role is to help students improve their academic performance and stay on track.
Be specific, actionable, and supportive. Never be generic or vague.
Always prioritize urgent concerns (failing grades, low attendance, imminent exams) first.
You strictly only answer queries related to student's academic performance or any of their \
enrolled course (Data Science / Full Stack Development).
Any unrelated query must be rejected politely."""


# -----------------------------------------------------------------------------
# MEMORY SECTION — appended to any prompt when memory is available
# Edit this to change how the coach uses past memory.
# -----------------------------------------------------------------------------
def _build_memory_section(
    memories: str | None,
    recent_summaries: str | None,
) -> str:
    """
    Builds the memory block appended to the bottom of any prompt.
    Returns an empty string if no memory is available.
    """
    if not memories and not recent_summaries:
        return ""

    lines = ["\n=== STUDENT MEMORY ==="]

    if memories:
        lines.append("\nLong-term facts about this student:")
        lines.append(memories)

    if recent_summaries:
        lines.append("\nRecent session summaries:")
        lines.append(recent_summaries)

    # --- MEMORY INSTRUCTIONS — edit to change how memory is used ---
    lines.append("""
=== MEMORY INSTRUCTIONS ===
- Use the above memory to personalise your response when relevant.
- Reference past patterns or commitments only when directly useful.
- Do NOT mention memory unnecessarily or remind the student of old information repeatedly.
- A student on their 5th session should feel meaningfully more understood than on their 1st.""")

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# PROMPT 1 — General (no data, no RAG)
# Used when route = "general"
# Edit the instructions block to change general conversation behaviour.
# -----------------------------------------------------------------------------
def build_general_prompt(
    student_name: str | None = None,
    memories: str | None = None,
    recent_summaries: str | None = None,
) -> str:
    name_line = (
        f"You are currently speaking with {student_name}." if student_name else ""
    )

    instructions = """Answer the student's question helpfully.
If they ask about their grades, attendance, or exams, let them know you can look that up.
If they ask about a course concept, let them know you can explain it in detail."""

    memory_section = _build_memory_section(memories, recent_summaries)

    return f"{COACH_PERSONA}\n{name_line}\n\n{instructions}{memory_section}"


# -----------------------------------------------------------------------------
# PROMPT 2 — Student data only
# Used when route = "student_data"
# Edit the INSTRUCTIONS block to change how the coach uses academic data.
# -----------------------------------------------------------------------------
def build_data_prompt(
    student_context: dict,
    memories: str | None = None,
    recent_summaries: str | None = None,
) -> str:
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
        if pct >= 85:
            status = "Good"
        elif pct >= 75:
            status = "Monitor"
        else:
            status = "Below threshold"
        attendance_text = (
            f"  Latest week ({att.get('week_of')}): {pct}%  [{status}]"
        )
    else:
        attendance_text = "  No attendance records available."

    # --- Format upcoming exams ---
    if ctx.get("upcoming_exams"):
        exams_text = "\n".join(
            f"  - {e['subject']} ({e.get('exam_type', 'Exam')}) on {e['exam_date']} "
            f"— {e['days_remaining']} day(s) away "
            + (
                "[HIGH PRIORITY]" if e["days_remaining"] <= 3
                else "[UPCOMING]" if e["days_remaining"] <= 7
                else "[INFORMATIONAL]"
            )
            for e in ctx["upcoming_exams"]
        )
    else:
        exams_text = "  No upcoming exams scheduled."

    memory_section = _build_memory_section(memories, recent_summaries)

    # --- INSTRUCTIONS — edit this block to change data-driven response style ---
    instructions = """- Use the data above to personalise your response.
- Mention weak subjects (low scores) and what to do about them.
- Flag low attendance if below 75%; mention it needs monitoring if 75–85%.
- Highlight exams within 7 days, with high urgency for exams within 3 days.
- Be specific — reference actual subjects, scores, and dates from the data.
- Do not invent any data not listed above."""

    return f"""{COACH_PERSONA}

You are speaking with {ctx.get('name', 'the student')} \
(Program: {ctx.get('program', 'N/A')}, Cohort: {ctx.get('cohort', 'N/A')}).

=== STUDENT ACADEMIC DATA ===

Recent Exam Scores:
{scores_text}

Attendance:
{attendance_text}

Upcoming Exams:
{exams_text}

=== INSTRUCTIONS ===
{instructions}{memory_section}"""


# -----------------------------------------------------------------------------
# PROMPT 3 — Knowledge base only (RAG, no personal data)
# Used when route = "knowledge_base"
# Edit the INSTRUCTIONS block to change how the coach uses retrieved content.
# -----------------------------------------------------------------------------
def build_knowledge_prompt(
    knowledge_context: str,
    student_name: str | None = None,
    memories: str | None = None,
    recent_summaries: str | None = None,
) -> str:
    name_line = (
        f"You are currently speaking with {student_name}." if student_name else ""
    )

    memory_section = _build_memory_section(memories, recent_summaries)

    # --- INSTRUCTIONS — edit this block to change RAG response style ---
    instructions = """- Answer using ONLY the retrieved content provided above.
- If the content does not contain enough information to answer fully, say so honestly.
- Do not hallucinate concepts, definitions, or examples beyond what is retrieved.
- Explain clearly and use simple examples where helpful."""

    return f"""{COACH_PERSONA}
{name_line}

=== RETRIEVED COURSE CONTENT ===
{knowledge_context}

=== INSTRUCTIONS ===
{instructions}{memory_section}"""


# -----------------------------------------------------------------------------
# PROMPT 4 — Combined (student data + RAG knowledge)
# Used when route = "both"
# Edit either INSTRUCTIONS block independently.
# -----------------------------------------------------------------------------
def build_combined_prompt(
    student_context: dict,
    knowledge_context: str,
    memories: str | None = None,
    recent_summaries: str | None = None,
) -> str:
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
        if pct >= 85:
            status = "Good"
        elif pct >= 75:
            status = "Monitor"
        else:
            status = "Below threshold"
        attendance_text = (
            f"  Latest week ({att.get('week_of')}): {pct}%  [{status}]"
        )
    else:
        attendance_text = "  No attendance records available."

    # --- Format upcoming exams ---
    if ctx.get("upcoming_exams"):
        exams_text = "\n".join(
            f"  - {e['subject']} ({e.get('exam_type', 'Exam')}) on {e['exam_date']} "
            f"— {e['days_remaining']} day(s) away "
            + (
                "[HIGH PRIORITY]" if e["days_remaining"] <= 3
                else "[UPCOMING]" if e["days_remaining"] <= 7
                else "[INFORMATIONAL]"
            )
            for e in ctx["upcoming_exams"]
        )
    else:
        exams_text = "  No upcoming exams scheduled."

    memory_section = _build_memory_section(memories, recent_summaries)

    # --- INSTRUCTIONS — edit each block independently ---
    data_instructions = """- Reference the student's actual scores, attendance, and exam dates.
- Flag any urgent areas (low scores, low attendance, imminent exams).
- Do not invent any data not listed above."""

    knowledge_instructions = """- Use the retrieved content to explain concepts relevant to the student's weak areas.
- Do not hallucinate explanations beyond what is retrieved.
- Tie the concept explanations back to the student's specific situation."""

    return f"""{COACH_PERSONA}

You are speaking with {ctx.get('name', 'the student')} \
(Program: {ctx.get('program', 'N/A')}, Cohort: {ctx.get('cohort', 'N/A')}).

=== STUDENT ACADEMIC DATA ===

Recent Exam Scores:
{scores_text}

Attendance:
{attendance_text}

Upcoming Exams:
{exams_text}

=== RETRIEVED COURSE CONTENT ===
{knowledge_context}

=== INSTRUCTIONS ===
Using the student data:
{data_instructions}

Using the retrieved content:
{knowledge_instructions}{memory_section}"""