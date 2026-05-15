import datetime
import os

import requests

FATHOM_API_BASE = os.environ.get("FATHOM_API_BASE", "https://api.fathom.video")
_MY_NAME_KEYWORDS = ["fidel", "salazar"]


def get_todays_action_items(my_email: str) -> dict:
    """
    Fetch action items from today's Fathom recordings via the Fathom REST API.
    Returns {"mine": [...], "others": [...], "meetings_checked": N}.

    Requires FATHOM_API_KEY env var (Settings → API in the Fathom web app).
    Gracefully returns empty results if the API key is absent or calls fail.
    """
    api_key = os.environ.get("FATHOM_API_KEY")
    if not api_key:
        print("FATHOM_API_KEY not set — skipping Fathom data.")
        return {"mine": [], "others": [], "meetings_checked": 0}

    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    today = datetime.date.today().isoformat()

    calls = _list_todays_calls(headers, today)
    if calls is None:
        return {"mine": [], "others": [], "meetings_checked": 0}

    mine, others = [], []
    for call in calls:
        title = call.get("title") or call.get("name") or "Unknown Meeting"
        action_items = call.get("action_items") or []

        # If action_items not embedded, try fetching per-call detail
        if not action_items and call.get("id"):
            action_items = _fetch_call_action_items(headers, call["id"])

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

    return {"mine": mine, "others": others, "meetings_checked": len(calls)}


def _list_todays_calls(headers: dict, today: str) -> list | None:
    """Return raw calls list for today, or None on failure."""
    params = {
        "from": f"{today}T00:00:00Z",
        "to": f"{today}T23:59:59Z",
        "include_action_items": "true",
        "limit": 50,
    }
    try:
        resp = requests.get(
            f"{FATHOM_API_BASE}/v1/calls",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("calls") or data.get("data") or data.get("results") or []
    except requests.RequestException as exc:
        print(f"Fathom /v1/calls failed: {exc}")
        return None


def _fetch_call_action_items(headers: dict, call_id: str) -> list:
    """Fetch action items for a single call from /v1/calls/{id}."""
    try:
        resp = requests.get(
            f"{FATHOM_API_BASE}/v1/calls/{call_id}",
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("action_items") or []
    except requests.RequestException:
        return []
