import os

from googleapiclient.discovery import build


def _build_gmail_service(credentials):
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def search_gmail_for_meeting(credentials, meeting: dict, user_email: str) -> list[dict]:
    """Search Gmail for emails related to this meeting's attendees and title."""
    service = _build_gmail_service(credentials)
    seen_ids = set()
    results = []

    attendees = [
        a["email"] for a in meeting.get("attendees", [])
        if a.get("email", "").lower() != user_email.lower()
    ]

    for email_addr in attendees[:5]:
        query = f"(from:{email_addr} OR to:{email_addr}) newer_than:30d"
        try:
            resp = service.users().messages().list(userId="me", q=query, maxResults=6).execute()
            for msg in resp.get("messages", []):
                if msg["id"] in seen_ids:
                    continue
                seen_ids.add(msg["id"])
                data = service.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute()
                headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
                results.append({
                    "from": headers.get("From", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "snippet": data.get("snippet", "")[:250],
                })
        except Exception as e:
            print(f"Gmail attendee search error ({email_addr}): {e}")

    # Also search by meeting title keywords
    keywords = " ".join(meeting.get("summary", "").split()[:4])
    if keywords:
        query = f'subject:"{keywords}" newer_than:60d'
        try:
            resp = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
            for msg in resp.get("messages", []):
                if msg["id"] in seen_ids:
                    continue
                seen_ids.add(msg["id"])
                data = service.users().messages().get(
                    userId="me", id=msg["id"], format="metadata",
                    metadataHeaders=["From", "Subject", "Date"]
                ).execute()
                headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
                results.append({
                    "from": headers.get("From", ""),
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "snippet": data.get("snippet", "")[:250],
                })
        except Exception as e:
            print(f"Gmail title search error: {e}")

    return results


def search_notion_for_meeting(meeting: dict) -> list[dict]:
    """Search Notion for pages related to this meeting."""
    token = os.environ.get("NOTION_API_TOKEN")
    if not token:
        return []

    title = meeting.get("summary", "")
    if not title:
        return []

    try:
        from notion_client import Client
        client = Client(auth=token)
        results = client.search(
            query=title,
            filter={"property": "object", "value": "page"},
            page_size=6,
        ).get("results", [])

        pages = []
        for page in results:
            props = page.get("properties", {})
            page_title = ""
            for prop in props.values():
                if prop.get("type") == "title":
                    page_title = "".join(t.get("plain_text", "") for t in prop.get("title", []))
                    break
            pages.append({
                "title": page_title or "Untitled",
                "url": page.get("url", ""),
                "last_edited": page.get("last_edited_time", "")[:10],
            })
        return pages
    except Exception as e:
        print(f"Notion search error: {e}")
        return []


def research_meeting(credentials, meeting: dict) -> dict:
    """Gather all context for a meeting from Gmail and Notion."""
    user_email = os.environ.get("USER_EMAIL", os.environ.get("RECIPIENT_EMAIL", ""))

    print("  Searching Gmail for relevant emails...")
    emails = search_gmail_for_meeting(credentials, meeting, user_email)
    print(f"  Found {len(emails)} relevant emails")

    print("  Searching Notion for relevant notes...")
    notion_pages = search_notion_for_meeting(meeting)
    print(f"  Found {len(notion_pages)} Notion pages")

    return {"emails": emails, "notion_pages": notion_pages}
