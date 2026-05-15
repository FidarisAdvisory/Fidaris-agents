import os

_MY_NAME_KEYWORDS = ["fidel", "salazar"]

# Default DB IDs — can be overridden via env vars
_DEFAULT_PERSONAL_DB = "0da18ecdd5ec4d2c9b92a9dba910e86d"
_DEFAULT_CEMEX_DB = "e0b828baf9c744bdae9627d5edf6c92b"


def get_all_action_items() -> dict:
    """
    Query both Notion action-item databases for open items.
    Returns {"mine": [...], "others": [...]}.

    Requires NOTION_API_TOKEN env var.
    Optional overrides: NOTION_ACTION_ITEMS_DB_ID, NOTION_CEMEX_TRACKER_DB_ID, NOTION_USER_ID.
    """
    token = os.environ.get("NOTION_API_TOKEN")
    if not token:
        print("NOTION_API_TOKEN not set — skipping Notion action items.")
        return {"mine": [], "others": []}

    try:
        from notion_client import Client
    except ImportError:
        print("notion-client not installed.")
        return {"mine": [], "others": []}

    client = Client(auth=token)
    my_user_id = os.environ.get(
        "NOTION_USER_ID", "530c64db-6e35-4e3c-8a79-5754869e83cc"
    )
    mine, others = [], []

    # Personal Action Items Tracker
    personal_db = os.environ.get("NOTION_ACTION_ITEMS_DB_ID", _DEFAULT_PERSONAL_DB)
    for item in _query_personal_tracker(client, personal_db, my_user_id):
        (mine if item["is_mine"] else others).append(item)

    # CEMEX Action Items Tracker
    cemex_db = os.environ.get("NOTION_CEMEX_TRACKER_DB_ID", _DEFAULT_CEMEX_DB)
    for item in _query_cemex_tracker(client, cemex_db):
        (mine if item["is_mine"] else others).append(item)

    return {"mine": mine, "others": others}


def _plain_text(prop_value: list) -> str:
    return "".join(t.get("plain_text", "") for t in prop_value)


def _query_personal_tracker(client, database_id: str, my_user_id: str) -> list:
    """Query the Fidel Action Items Tracker for open items (Status != Done)."""
    try:
        response = client.databases.query(
            database_id=database_id,
            filter={"property": "Status", "status": {"does_not_equal": "Done"}},
            page_size=100,
        )
    except Exception as exc:
        print(f"Personal tracker query failed: {exc}")
        return []

    results = []
    for page in response.get("results", []):
        props = page.get("properties", {})

        title = ""
        for prop in props.values():
            if prop.get("type") == "title":
                title = _plain_text(prop.get("title", []))
                break
        if not title:
            continue

        status = (
            (props.get("Status") or {}).get("status") or {}
        ).get("name", "")
        project = ((props.get("Client") or {}).get("select") or {}).get("name", "")
        category = ((props.get("Category") or {}).get("select") or {}).get("name", "")
        source = _plain_text((props.get("Source") or {}).get("rich_text", []))

        owner_people = (props.get("Owner") or {}).get("people", [])
        is_mine = any(p.get("id") == my_user_id for p in owner_people)
        owner_name = ", ".join(p.get("name", "") for p in owner_people) or "Unassigned"

        results.append({
            "task": title,
            "project": project or "Other",
            "category": category,
            "status": status,
            "owner": owner_name,
            "source": source,
            "is_mine": is_mine,
            "url": page.get("url", ""),
            "tracker": "Fidel Action Items",
        })
    return results


def _query_cemex_tracker(client, database_id: str) -> list:
    """Query the CEMEX Action Items Tracker for open items (Status != Done)."""
    try:
        response = client.databases.query(
            database_id=database_id,
            filter={"property": "Status", "status": {"does_not_equal": "Done"}},
            page_size=100,
        )
    except Exception as exc:
        print(f"CEMEX tracker query failed: {exc}")
        return []

    results = []
    for page in response.get("results", []):
        props = page.get("properties", {})

        title = ""
        for prop in props.values():
            if prop.get("type") == "title":
                title = _plain_text(prop.get("title", []))
                break
        if not title:
            continue

        status = (
            (props.get("Status") or {}).get("status") or {}
        ).get("name", "")
        tower = ((props.get("Tower") or {}).get("select") or {}).get("name", "")
        owner = _plain_text((props.get("Owner") or {}).get("rich_text", []))
        notes = _plain_text(
            (props.get("Notes / Follow-up Comments") or {}).get("rich_text", [])
        )

        is_mine = any(kw in owner.lower() for kw in _MY_NAME_KEYWORDS)

        results.append({
            "task": title,
            "project": f"CEMEX — {tower}" if tower else "CEMEX",
            "category": tower,
            "status": status,
            "owner": owner or "TBD",
            "notes": notes,
            "is_mine": is_mine,
            "url": page.get("url", ""),
            "tracker": "CEMEX Action Items",
        })
    return results
