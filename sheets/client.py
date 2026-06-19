import os
import json
import streamlit as st
from datetime import datetime, date
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]


def _get_client() -> gspread.Client:
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),  # ← add dict() wrapper
        scopes=SCOPES,
    )
    return gspread.authorize(creds)


def _get_spreadsheet() -> gspread.Spreadsheet:
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    client = _get_client()
    return client.open_by_key(spreadsheet_id)


# --------------------------------------------------------------------------- #
#  Per-sheet fetch functions
# --------------------------------------------------------------------------- #

def fetch_roster(student_id: str) -> dict | None:
    """Return the roster row for a given student_id, or None if not found."""
    sheet = _get_spreadsheet().worksheet("roster")
    records = sheet.get_all_records()
    for row in records:
        if str(row["student_id"]) == str(student_id):
            return row
    return None


def fetch_all_students() -> list[dict]:
    """Return all students from the roster sheet."""
    sheet = _get_spreadsheet().worksheet("roster")
    return sheet.get_all_records()


def fetch_exam_scores(student_id: str) -> list[dict]:
    """Return all exam score rows for a student, sorted by date descending."""
    sheet = _get_spreadsheet().worksheet("exam_scores")
    records = sheet.get_all_records()
    scores = [r for r in records if str(r["student_id"]) == str(student_id)]
    scores.sort(key=lambda x: x.get("date", ""), reverse=True)
    return scores


def fetch_attendance(student_id: str) -> list[dict]:
    """Return all attendance rows for a student, sorted by week descending."""
    sheet = _get_spreadsheet().worksheet("attendance")
    records = sheet.get_all_records()
    rows = [r for r in records if str(r["student_id"]) == str(student_id)]
    rows.sort(key=lambda x: x.get("week_of", ""), reverse=True)
    return rows


def fetch_exam_schedule(student_id: str) -> list[dict]:
    """Return upcoming exams for a student with days_remaining calculated."""
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
#  Composite: build full student context
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
    # Keep the 10 most recent scores
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

    return {
        "student_id": student_id,
        "name": roster.get("name"),
        "program": roster.get("program"),
        "cohort": roster.get("cohort"),
        "recent_scores": recent_scores,
        "latest_attendance": latest_attendance,
        "upcoming_exams": upcoming_exams,
    }