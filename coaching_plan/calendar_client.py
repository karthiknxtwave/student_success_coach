import streamlit as st
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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
) -> dict:
    """
    Create a Calendar event for an approved coaching session.
    Only the coach is invited — students are never added.

    Args:
        start_time: ISO 8601 datetime string, e.g. "2026-06-21T10:00:00"
        coach_id:   Which coach's calendar to use. Defaults to the single
                    configured coach; accepted now so multi-coach support
                    later requires no caller-side changes.

    Returns:
        {"event_id": str, "link": str}
        event_id must be persisted (e.g. in daily_plans) to allow cancellation
        later via cancel_coaching_event().
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

    return {
        "event_id": created.get("id", ""),
        "link": created.get("htmlLink", ""),
    }


def cancel_coaching_event(event_id: str, coach_id: str = DEFAULT_COACH_ID) -> bool:
    """
    Cancel (delete) a previously created coaching event.

    Args:
        event_id: The Calendar event ID returned by create_coaching_event().
        coach_id: Which coach's calendar to use.

    Returns:
        True if the event was deleted or was already gone, False on a real error.
    """
    if not event_id:
        return True  # nothing to cancel

    cfg = st.secrets["google_calendar"]
    service = _get_service(coach_id)

    try:
        service.events().delete(
            calendarId=cfg.get("CALENDAR_ID", "primary"),
            eventId=event_id,
        ).execute()
        return True
    except HttpError as e:
        if e.resp.status in (404, 410):
            # Already deleted/gone — treat as success
            return True
        print(f"[calendar] Failed to cancel event {event_id}: {e}")
        return False


def _add_minutes(iso_datetime: str, minutes: int) -> str:
    from datetime import datetime, timedelta
    dt = datetime.fromisoformat(iso_datetime)
    return (dt + timedelta(minutes=minutes)).isoformat()