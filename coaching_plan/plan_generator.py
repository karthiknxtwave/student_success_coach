"""
Deterministic daily coaching plan generation.
No LLM involved — all scoring, session typing, and capacity-fitting is rule-based.
"""

# ---------------------------------------------------------------------------
# CONFIG — edit these to tune planning behaviour
# ---------------------------------------------------------------------------
COACH_DAILY_CAPACITY = 2   # Max coaching sessions per day. Raise this as coaches scale.

SEVERITY_SCORES = {"high": 3, "medium": 2, "low": 1}
URGENCY_SCORES = {"today": 3, "tomorrow": 2, "this_week": 1}

# signal_type → primary session type (priority order matters for tie-breaks)
SESSION_TYPE_MAP = {
    "dropout_risk":     "Retention Intervention",
    "performance_risk": "Academic Recovery",
    "attendance_risk":  "Attendance Intervention",
    "exam_risk":        "Exam Preparation",
    "stress_risk":       "Stress Check-In",
    "motivation_risk":  "Motivation Support",
    "engagement_risk":  "Engagement Recovery",
}
# Order above = priority order. dropout_risk wins if present alongside anything else.
SESSION_TYPE_PRIORITY = list(SESSION_TYPE_MAP.keys())

DURATION_BY_SIGNAL_COUNT = {
    1: 30,
    2: 60,
}
DEFAULT_DURATION = 90  # 3 or more signals
# ---------------------------------------------------------------------------


def _signal_priority(signal: dict) -> int:
    """severity_score + urgency_score for one signal."""
    sev = SEVERITY_SCORES.get(signal.get("severity"), 0)
    urg = URGENCY_SCORES.get(signal.get("urgency"), 0)
    return sev + urg


def _session_duration(signal_count: int) -> int:
    return DURATION_BY_SIGNAL_COUNT.get(signal_count, DEFAULT_DURATION)


def _session_type(signals: list[dict]) -> str:
    """Pick the most appropriate session type based on signal priority order."""
    present_types = {s["signal_type"] for s in signals}
    for signal_type in SESSION_TYPE_PRIORITY:
        if signal_type in present_types:
            return SESSION_TYPE_MAP[signal_type]
    return "General Check-In"  # fallback, should not normally happen


def _build_reason(signals: list[dict]) -> str:
    """Concatenate signal reasons into one readable paragraph."""
    return " ".join(s.get("reason", "").strip() for s in signals if s.get("reason"))


def _group_signals_by_student(open_signals: list[dict]) -> dict[str, list[dict]]:
    grouped = {}
    for signal in open_signals:
        sid = signal["student_id"]
        grouped.setdefault(sid, []).append(signal)
    return grouped


def build_daily_plan(
    open_signals: list[dict],
    student_lookup: dict[str, str],
    capacity: int = COACH_DAILY_CAPACITY,
) -> dict:
    """
    Build a prioritized daily coaching plan from open signals.

    Args:
        open_signals:   List of signal dicts (actioned == False), each with
                         student_id, signal_type, severity, urgency, reason.
        student_lookup: {student_id: student_name} for display purposes.
        capacity:       Max sessions that fit today.

    Returns:
        {
            "scheduled": [ {student_id, student_name, priority_score,
                             session_type, duration_minutes, signals, reason}, ... ],
            "deferred":  [ {... same fields ..., defer_reason}, ... ],
        }
        Both lists are sorted by priority_score descending.
    """
    grouped = _group_signals_by_student(open_signals)

    students = []
    for student_id, signals in grouped.items():
        priority_score = sum(_signal_priority(s) for s in signals)
        students.append({
            "student_id": student_id,
            "student_name": student_lookup.get(student_id, student_id),
            "priority_score": priority_score,
            "session_type": _session_type(signals),
            "duration_minutes": _session_duration(len(signals)),
            "signals": [s["signal_type"] for s in signals],
            "reason": _build_reason(signals),
        })

    # Highest priority first
    students.sort(key=lambda s: s["priority_score"], reverse=True)

    scheduled = students[:capacity]
    deferred = students[capacity:]

    for student in deferred:
        student["defer_reason"] = (
            "Higher-priority students exhausted today's coaching capacity."
        )

    return {"scheduled": scheduled, "deferred": deferred}