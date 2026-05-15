import datetime
import os

import requests

FATHOM_API_BASE = os.environ.get("FATHOM_API_BASE", "https://api.fathom.ai/external/v1")
_MY_NAME_KEYWORDS = ["fidel", "salazar"]


def get_todays_action_items(my_email: str) -> dict:
    """
    Fetch action items from today's Fathom recordings.
    Returns {"mine": [...], "others": [...], "meetings_checked": N}.

    Requires FATHOM_API_KEY env var (Fathom web app → Settings → API).
    Auth: X-Api-Key header. Endpoint: GET /meetings.
    """
    api_key = os.environ.get("FATHOM_API_KEY")
    if not api_key:
        print("FATHOM_API_KEY not set — skipping Fathom data.")
        return {"mine": [], "others": [], "meetings_checked": 0}

    headers = {"X-Api-Key": api_key, "Accept": "application/json"}
    today = datetime.date.today().isoformat()

    meetings = _list_todays_meetings(headers, today)
    if meetings is None:
        return {"mine": [], "others": [], "meetings_checked": 0}

    print(f"  Fathom: {len(meetings)} meeting(s) found for {today}")
    mine, others = [], []

    for meeting in meetings:
        title = meeting.get("title") or meeting.get("name") or "Unknown Meeting"
        action_items = meeting.get("action_items") or []

        # If not embedded, try fetching from the per-meeting detail endpoint
        if not action_items:
            meeting_id = meeting.get("id") or meeting.get("recording_id")
            if meeting_id:
                action_items = _fetch_meeting_action_items(headers, meeting_id)

        for item in action_items:
            text = (
                item.get("text")
                or item.get("content")
                or item.get("action_item")
                or ""
            ).strip()
            if not text:
                continue

            assignee = (
                item.get("assigned_to")
                or item.get("assignee")
                or item.get("owner")
                or ""
            )
            task = {
                "task": text,
                "meeting": title,
                "assignee": assignee,
                "date": today,
                "source": "Fathom",
            }
            al = assignee.lower()
            if my_email.lower() in al or any(kw in al for kw in _MY_NAME_KEYWORDS):
                mine.append(task)
            else:
                others.append(task)

    return {"mine": mine, "others": others, "meetings_checked": len(meetings)}


def _list_todays_meetings(headers: dict, today: str) -> list | None:
    """Return raw meetings list for today, or None on failure."""
    params = {
        "from": f"{today}T00:00:00Z",
        "to": f"{today}T23:59:59Z",
        "include_action_items": "true",
        "limit": 50,
    }
    try:
        resp = requests.get(
            f"{FATHOM_API_BASE}/meetings",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        # Handle both list and paginated object responses
        if isinstance(data, list):
            return data
        return data.get("meetings") or data.get("data") or data.get("results") or []
    except requests.HTTPError as exc:
        print(f"Fathom /meetings HTTP error {exc.response.status_code}: {exc.response.text[:300]}")
        return None
    except requests.RequestException as exc:
        print(f"Fathom /meetings request failed: {exc}")
        return None


def _fetch_meeting_action_items(headers: dict, meeting_id: str) -> list:
    """Fetch action items for a single meeting from /meetings/{id}."""
    for path in (f"/meetings/{meeting_id}", f"/recordings/{meeting_id}"):
        try:
            resp = requests.get(
                f"{FATHOM_API_BASE}{path}",
                headers=headers,
                timeout=30,
            )
            if resp.ok:
                return resp.json().get("action_items") or []
        except requests.RequestException:
            continue
    return []
