import base64
import os

from googleapiclient.discovery import build


def _build_gmail_service(credentials):
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _extract_email_text(message: dict, max_chars: int = 2000) -> str:
    """Extract plain text body from a Gmail message payload."""
    def _get_parts(payload):
        parts = []
        if payload.get("mimeType") == "text/plain":
            data = payload.get("body", {}).get("data", "")
            if data:
                decoded = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="ignore")
                parts.append(decoded)
        for part in payload.get("parts", []):
            parts.extend(_get_parts(part))
        return parts

    texts = _get_parts(message.get("payload", {}))
    return "\n".join(texts)[:max_chars]


def search_gmail_for_meeting(credentials, meeting: dict, user_email: str) -> list[dict]:
    """Search Gmail inbox for emails related to this meeting's attendees and title."""
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


def search_fathom_for_meeting(credentials, meeting: dict) -> list[dict]:
    """Search the Fathom Gmail label for past meeting notes related to this meeting."""
    service = _build_gmail_service(credentials)
    seen_ids = set()
    results = []

    search_terms = []
    for attendee in meeting.get("attendees", [])[:5]:
        name = attendee.get("name", "")
        email = attendee.get("email", "")
        if name and "@" not in name:
            parts = name.strip().split()
            if parts:
                search_terms.append(parts[-1])  # last name
            if len(parts) > 1:
                search_terms.append(parts[0])   # first name as backup
        elif email:
            local = email.split("@")[0]
            if len(local) > 3:
                search_terms.append(local)

    title_words = [w for w in meeting.get("summary", "").split() if len(w) > 4]
    search_terms.extend(title_words[:2])

    seen_terms: set = set()
    unique_terms = []
    for t in search_terms:
        if t.lower() not in seen_terms:
            seen_terms.add(t.lower())
            unique_terms.append(t)

    for term in unique_terms[:4]:
        query = f'label:Fathom "{term}"'
        try:
            resp = service.users().messages().list(userId="me", q=query, maxResults=5).execute()
            for msg in resp.get("messages", []):
                if msg["id"] in seen_ids:
                    continue
                seen_ids.add(msg["id"])
                data = service.users().messages().get(
                    userId="me", id=msg["id"], format="full"
                ).execute()
                headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
                body = _extract_email_text(data, max_chars=2000)
                results.append({
                    "subject": headers.get("Subject", ""),
                    "date": headers.get("Date", ""),
                    "body": body or data.get("snippet", "")[:500],
                })
                print(f"  Fathom note found: {headers.get('Subject', '')[:60]}")
        except Exception as e:
            print(f"Fathom search error ({term}): {e}")

    print(f"  Fathom: {len(results)} note(s) found")
    return results


def search_notion_for_meeting(meeting: dict) -> list[dict]:
    """Search Notion for meeting notes related to this meeting by title and attendee names."""
    token = os.environ.get("NOTION_API_TOKEN")
    if not token:
        return []

    try:
        from notion_client import Client
        client = Client(auth=token)
    except ImportError:
        return []

    queries = []
    title = meeting.get("summary", "").strip()
    if title:
        queries.append(title)

    for attendee in meeting.get("attendees", [])[:4]:
        name = attendee.get("name", "")
        if name and "@" not in name and len(name) > 3:
            queries.append(name)

    seen_urls: set = set()
    pages = []

    for query in queries[:5]:
        try:
            results = client.search(
                query=query,
                filter={"property": "object", "value": "page"},
                page_size=5,
            ).get("results", [])

            for page in results:
                url = page.get("url", "")
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                props = page.get("properties", {})
                page_title = ""
                for prop in props.values():
                    if prop.get("type") == "title":
                        page_title = "".join(t.get("plain_text", "") for t in prop.get("title", []))
                        break
                pages.append({
                    "title": page_title or "Untitled",
                    "url": url,
                    "last_edited": page.get("last_edited_time", "")[:10],
                })
        except Exception as e:
            print(f"Notion search error ({query}): {e}")

    return pages


def research_meeting(credentials, meeting: dict) -> dict:
    """Gather all context for a meeting from Gmail inbox, Fathom notes, and Notion."""
    user_email = os.environ.get("USER_EMAIL", os.environ.get("RECIPIENT_EMAIL", ""))

    print("  Searching Gmail for relevant emails...")
    emails = search_gmail_for_meeting(credentials, meeting, user_email)
    print(f"  Found {len(emails)} relevant email(s)")

    print("  Searching Fathom folder for past meeting notes...")
    fathom_notes = search_fathom_for_meeting(credentials, meeting)

    print("  Searching Notion for relevant notes and meeting pages...")
    notion_pages = search_notion_for_meeting(meeting)
    print(f"  Found {len(notion_pages)} Notion page(s)")

    return {
        "emails": emails,
        "fathom_notes": fathom_notes,
        "notion_pages": notion_pages,
    }
