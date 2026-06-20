"""
Google Calendar integration via OAuth2 (personal Gmail account).

CURRENT STATE (single coach):
  Refresh token lives in st.secrets under [google_calendar]. All events are
  created on that one account's calendar.

FUTURE STATE (multi-coach):
  Replace _get_credentials() to look up the refresh token by coach_id from a
  coach_tokens sheet/table instead of st.secrets. Every function below already
  accepts coach_id, so no caller-side changes will be needed when that swap
  happens — only this file changes.

One-time setup required before this works:
1. Run generate_calendar_token.py locally (browser consent) to obtain a
   refresh token.
2. Paste the resulting refresh token into st.secrets under [google_calendar].

Required secrets.toml block:

[google_calendar]
CLIENT_ID = "..."
CLIENT_SECRET = "..."
REFRESH_TOKEN = "..."
CALENDAR_ID = "primary"   # or a specific calendar id
COACH_EMAIL = "coach@example.com"
"""

import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]

DEFAULT_COACH_ID = "coach_1"  # single-coach placeholder; see module docstring


def _get_credentials(coach_id: str = DEFAULT_COACH_ID) -> Credentials:
    """
    Returns OAuth2 credentials for the given coach.

    Currently ignores coach_id and always reads from st.secrets, since there
    is only one coach. When multi-coach support is added, swap the body of
    this function to look up the refresh token by coach_id (e.g. from a
    coach_tokens sheet) — no other function in this file needs to change.
    """
    cfg = st.secrets["google_calendar"]
    return Credentials(
        token=None,
        refresh_token=cfg["REFRESH_TOKEN"],
        client_id=cfg["CLIENT_ID"],
        client_secret=cfg["CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )


def _get_service(coach_id: str = DEFAULT_COACH_ID):
    creds = _get_credentials(coach_id)
    return build("calendar", "v3", credentials=creds)


def create_coaching_event(
    student_name: str,
    student_id: str,
    session_type: str,
    signals: list[str],
    reason: str,
    start_time: str,
    duration_minutes: int,
    coach_id: str = DEFAULT_COACH_ID,
) -> str:
    """
    Create a Calendar event for an approved coaching session.
    Only the coach is invited — students are never added.

    Args:
        start_time: ISO 8601 datetime string, e.g. "2026-06-21T10:00:00"
        coach_id:   Which coach's calendar to use. Defaults to the single
                    configured coach; accepted now so multi-coach support
                    later requires no caller-side changes.

    Returns:
        The created event's HTML link (for confirmation/display).
    """
    cfg = st.secrets["google_calendar"]
    service = _get_service(coach_id)

    signals_text = "\n".join(f"- {s}" for s in signals)
    description = (
        f"Session Type: {session_type}\n\n"
        f"Signals:\n{signals_text}\n\n"
        f"Reason:\n{reason}"
    )

    start_dt = start_time
    end_dt = _add_minutes(start_time, duration_minutes)

    event = {
        "summary": f"Student Success Coaching - {student_name}",
        "description": description,
        "start": {"dateTime": start_dt, "timeZone": "Asia/Kolkata"},
        "end": {"dateTime": end_dt, "timeZone": "Asia/Kolkata"},
        "attendees": [{"email": cfg["COACH_EMAIL"]}],
    }

    created = service.events().insert(
        calendarId=cfg.get("CALENDAR_ID", "primary"),
        body=event,
    ).execute()

    return created.get("htmlLink", "")


def _add_minutes(iso_datetime: str, minutes: int) -> str:
    from datetime import datetime, timedelta
    dt = datetime.fromisoformat(iso_datetime)
    return (dt + timedelta(minutes=minutes)).isoformat()