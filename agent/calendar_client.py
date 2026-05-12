import datetime
import os

import pytz
from googleapiclient.discovery import build


def _build_service(credentials):
    return build("calendar", "v3", credentials=credentials, cache_discovery=False)


def get_events_for_date(service, target_date: datetime.date, tz: pytz.BaseTzInfo) -> list[dict]:
    """Fetch all events from the primary calendar on target_date."""
    day_start = tz.localize(datetime.datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0))
    day_end = day_start + datetime.timedelta(days=1)

    result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=day_start.isoformat(),
            timeMax=day_end.isoformat(),
            maxResults=50,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = []
    for item in result.get("items", []):
        start = item.get("start", {})
        end = item.get("end", {})
        is_all_day = "date" in start and "dateTime" not in start

        events.append(
            {
                "summary": item.get("summary", "(No title)"),
                "start": start.get("dateTime", start.get("date", "")),
                "end": end.get("dateTime", end.get("date", "")),
                "is_all_day": is_all_day,
                "location": item.get("location", ""),
                "description": (item.get("description") or "")[:200],
            }
        )
    return events


def get_calendar_data(credentials) -> dict:
    """Return today's and tomorrow's events with date strings."""
    timezone_name = os.environ.get("USER_TIMEZONE", "America/Chicago")
    tz = pytz.timezone(timezone_name)
    now = datetime.datetime.now(tz)
    today = now.date()
    tomorrow = today + datetime.timedelta(days=1)

    service = _build_service(credentials)
    return {
        "today": get_events_for_date(service, today, tz),
        "tomorrow": get_events_for_date(service, tomorrow, tz),
        "today_date": today.strftime("%A, %B %-d, %Y"),
        "tomorrow_date": tomorrow.strftime("%A, %B %-d, %Y"),
        "current_time": now.strftime("%I:%M %p %Z"),
    }
