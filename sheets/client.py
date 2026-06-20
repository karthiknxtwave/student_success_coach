import os
import json
import streamlit as st
from datetime import datetime, date
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",  # upgraded from readonly to allow writes
]


def _get_client() -> gspread.Client:
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def _get_spreadsheet() -> gspread.Spreadsheet:
    spreadsheet_id = st.secrets["app"]["SPREADSHEET_ID"]
    client = _get_client()
    return client.open_by_key(spreadsheet_id)


# --------------------------------------------------------------------------- #
#  Per-sheet fetch functions (unchanged)
# --------------------------------------------------------------------------- #

def fetch_roster(student_id: str) -> dict | None:
    """Return the roster row for a given student_id, or None if not found."""
    print("fetching roster row")
    sheet = _get_spreadsheet().worksheet("roster")
    records = sheet.get_all_records()
    for row in records:
        if str(row["student_id"]) == str(student_id):
            return row
    return None


def fetch_all_students() -> list[dict]:
    """Return all students from the roster sheet."""
    print("fetching students list")
    sheet = _get_spreadsheet().worksheet("roster")
    return sheet.get_all_records()


def fetch_exam_scores(student_id: str) -> list[dict]:
    """Return all exam score rows for a student, sorted by date descending."""
    print("fetching exam scores for the student")
    sheet = _get_spreadsheet().worksheet("exam_scores")
    records = sheet.get_all_records()
    scores = [r for r in records if str(r["student_id"]) == str(student_id)]
    scores.sort(key=lambda x: x.get("date", ""), reverse=True)
    return scores


def fetch_attendance(student_id: str) -> list[dict]:
    """Return all attendance rows for a student, sorted by week descending."""
    print("fetching student attendance data")
    sheet = _get_spreadsheet().worksheet("attendance")
    records = sheet.get_all_records()
    rows = [r for r in records if str(r["student_id"]) == str(student_id)]
    rows.sort(key=lambda x: x.get("week_of", ""), reverse=True)
    return rows


def fetch_exam_schedule(student_id: str) -> list[dict]:
    """Return upcoming exams for a student with days_remaining calculated."""
    print("fetching exam schedule")
    sheet = _get_spreadsheet().worksheet("exam_schedule")
    records = sheet.get_all_records()
    today = date.today()
    upcoming = []
    for row in records:
        if str(row["student_id"]) != str(student_id):
            continue
        try:
            exam_date = datetime.strptime(str(row["exam_date"]), "%Y-%m-%d").date()
            days_remaining = (exam_date - today).days
            if days_remaining >= 0:
                upcoming.append({
                    "subject": row["subject"],
                    "exam_date": str(row["exam_date"]),
                    "exam_type": row.get("exam_type", ""),
                    "days_remaining": days_remaining,
                })
        except ValueError:
            continue
    upcoming.sort(key=lambda x: x["days_remaining"])
    return upcoming


# --------------------------------------------------------------------------- #
#  Composite: build full student context (unchanged)
# --------------------------------------------------------------------------- #

def build_student_context(student_id: str) -> dict | None:
    """
    Fetch all sheets and return a unified context object.
    Returns None if the student_id is not found in the roster.
    """
    roster = fetch_roster(student_id)
    if roster is None:
        return None

    scores = fetch_exam_scores(student_id)
    recent_scores = [
        {
            "subject": s["subject"],
            "score": s["score"],
            "max_score": s["max_score"],
            "date": s["date"],
        }
        for s in scores[:10]
    ]

    attendance_rows = fetch_attendance(student_id)
    latest_attendance = None
    if attendance_rows:
        latest = attendance_rows[0]
        latest_attendance = {
            "week_of": latest.get("week_of"),
            "attendance_pct": latest.get("attendance_pct"),
        }

    upcoming_exams = fetch_exam_schedule(student_id)

    print("fetched complete student data")

    return {
        "student_id": student_id,
        "name": roster.get("name"),
        "program": roster.get("program"),
        "cohort": roster.get("cohort"),
        "recent_scores": recent_scores,
        "latest_attendance": latest_attendance,
        "upcoming_exams": upcoming_exams,
    }


# --------------------------------------------------------------------------- #
#  Signals sheet functions (unchanged)
# --------------------------------------------------------------------------- #

SIGNALS_SHEET = "signals"
SIGNALS_HEADERS = [
    "student_id", "signal_type", "severity",
    "urgency", "reason", "timestamp", "actioned",
]


def _get_signals_sheet() -> gspread.Worksheet:
    """Return the signals worksheet, creating it with headers if it doesn't exist."""
    spreadsheet = _get_spreadsheet()
    try:
        return spreadsheet.worksheet(SIGNALS_SHEET)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=SIGNALS_SHEET, rows=1000, cols=10)
        sheet.append_row(SIGNALS_HEADERS)
        return sheet


def fetch_signals() -> list[dict]:
    """
    Return all signals from the signals sheet as a list of dicts.
    Each dict includes a 'row_index' key for actioning.
    """
    sheet = _get_signals_sheet()
    records = sheet.get_all_records()
    # Row index in sheet = record index + 2 (1 for header, 1 for 1-based indexing)
    return [
        {**record, "row_index": idx + 2}
        for idx, record in enumerate(records)
    ]


def fetch_open_signals() -> list[dict]:
    """Return only unactioned signals (actioned == false). Used for plan generation."""
    return [
        s for s in fetch_signals()
        if str(s.get("actioned", "false")).lower() == "false"
    ]


def append_signals(signals: list[dict], student_id: str) -> None:
    """
    Append new signals to the signals sheet with deduplication.
    Skips any signal_type that already has an unactioned signal for this student.

    Args:
        signals:    List of dicts with keys: signal_type, severity, urgency, reason
        student_id: The student's ID
    """
    if not signals:
        return

    sheet = _get_signals_sheet()

    # Fetch existing unactioned signal types for this student
    existing = sheet.get_all_records()
    unactioned_types = {
        str(r["signal_type"])
        for r in existing
        if str(r["student_id"]) == str(student_id)
        and str(r.get("actioned", "false")).lower() == "false"
    }

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S")
    rows_to_append = []

    for signal in signals:
        if signal["signal_type"] in unactioned_types:
            print(f"[signals] Skipping duplicate: {signal['signal_type']}")
            continue
        rows_to_append.append([
            student_id,
            signal["signal_type"],
            signal["severity"],
            signal["urgency"],
            signal["reason"],
            timestamp,
            "false",
        ])

    if rows_to_append:
        sheet.append_rows(rows_to_append)
        print(f"[signals] Stored {len(rows_to_append)} new signal(s).")


def update_signal_actioned(row_index: int) -> None:
    """
    Mark a signal as actioned by updating the 'actioned' column.

    Args:
        row_index: The 1-based sheet row index (included in fetch_signals results).
    """
    sheet = _get_signals_sheet()
    actioned_col = SIGNALS_HEADERS.index("actioned") + 1  # 1-based column index
    sheet.update_cell(row_index, actioned_col, "true")
    print(f"[signals] Row {row_index} marked as actioned.")


# --------------------------------------------------------------------------- #
#  Daily plans sheet functions (new — M7)
# --------------------------------------------------------------------------- #

DAILY_PLANS_SHEET = "daily_plans"
DAILY_PLANS_HEADERS = [
    "plan_date", "student_id", "student_name", "priority_score",
    "session_type", "duration_minutes", "reason", "status", "coach_id",
]
# status values: planned | approved | completed | deferred


def _get_daily_plans_sheet() -> gspread.Worksheet:
    """Return the daily_plans worksheet, creating it with headers if it doesn't exist."""
    spreadsheet = _get_spreadsheet()
    try:
        return spreadsheet.worksheet(DAILY_PLANS_SHEET)
    except gspread.WorksheetNotFound:
        sheet = spreadsheet.add_worksheet(title=DAILY_PLANS_SHEET, rows=1000, cols=10)
        sheet.append_row(DAILY_PLANS_HEADERS)
        return sheet


def fetch_daily_plans(plan_date: str | None = None) -> list[dict]:
    """
    Return daily plan rows, optionally filtered to one plan_date (YYYY-MM-DD).
    Each dict includes a 'row_index' key for status updates.
    """
    sheet = _get_daily_plans_sheet()
    records = sheet.get_all_records()
    rows = [
        {**record, "row_index": idx + 2}
        for idx, record in enumerate(records)
    ]
    if plan_date:
        rows = [r for r in rows if str(r.get("plan_date")) == plan_date]
    return rows


def append_daily_plans(plan_rows: list[dict], plan_date: str, coach_id: str) -> None:
    """
    Append approved plan rows to the daily_plans sheet.

    Args:
        plan_rows: List of dicts with keys: student_id, student_name,
                   priority_score, session_type, duration_minutes, reason, status
        plan_date: ISO date string, e.g. "2026-06-21"
        coach_id:  Coach identifier (single-coach placeholder for now)
    """
    if not plan_rows:
        return

    sheet = _get_daily_plans_sheet()
    rows_to_append = []

    for plan in plan_rows:
        rows_to_append.append([
            plan_date,
            plan["student_id"],
            plan["student_name"],
            plan["priority_score"],
            plan["session_type"],
            plan["duration_minutes"],
            plan["reason"],
            plan.get("status", "planned"),
            coach_id,
        ])

    sheet.append_rows(rows_to_append)
    print(f"[daily_plans] Stored {len(rows_to_append)} plan row(s) for {plan_date}.")


def update_plan_status(row_index: int, status: str) -> None:
    """
    Update the status of a single daily plan row.

    Args:
        row_index: The 1-based sheet row index (included in fetch_daily_plans results).
        status:    One of planned | approved | completed | deferred
    """
    sheet = _get_daily_plans_sheet()
    status_col = DAILY_PLANS_HEADERS.index("status") + 1  # 1-based column index
    sheet.update_cell(row_index, status_col, status)
    print(f"[daily_plans] Row {row_index} status set to '{status}'.")