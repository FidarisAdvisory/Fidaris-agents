import base64
import datetime
import os
import re
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pytz
from googleapiclient.discovery import build

from agent.action_items_notion_client import get_all_action_items
from agent.action_items_synthesizer import synthesize_action_items
from agent.auth import get_google_credentials
from agent.fathom_client import get_todays_action_items


def _build_html_wrapper(digest_html: str, today_date: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:620px;margin:24px auto;background:#fff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
    <div style="background:#1a1a2e;padding:20px 28px;">
      <p style="margin:0;color:#a0a8c0;font-size:12px;letter-spacing:1px;text-transform:uppercase;">Evening Action Items</p>
      <h1 style="margin:4px 0 0;color:#fff;font-size:20px;font-weight:600;">{today_date}</h1>
    </div>
    <div style="padding:24px 28px;color:#2d3748;font-size:15px;line-height:1.6;">
      {digest_html}
    </div>
    <div style="padding:16px 28px;background:#f8f9fb;border-top:1px solid #e8ecf0;">
      <p style="margin:0;color:#9aa5b4;font-size:12px;">Sent automatically by your Action Items Agent &mdash; Fidaris Advisory</p>
    </div>
  </div>
</body>
</html>"""


def _send_email(credentials, recipient: str, full_html: str, today_date: str) -> None:
    service = build("gmail", "v1", credentials=credentials, cache_discovery=False)
    plain = re.sub(r"&[a-z]+;", " ", re.sub(r"<[^>]+>", "", full_html)).strip()

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Action Items — {today_date}"
    msg["To"] = recipient
    msg["From"] = f"Action Items Agent <{os.environ.get('USER_EMAIL', recipient)}>"
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(full_html, "html"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"Email sent to {recipient}: Action Items — {today_date}")


def main() -> None:
    recipient = os.environ["RECIPIENT_EMAIL"]
    user_email = os.environ.get("USER_EMAIL", recipient)
    tz = pytz.timezone(os.environ.get("USER_TIMEZONE", "America/Chicago"))
    today_date = datetime.datetime.now(tz).strftime("%A, %B %-d, %Y")

    print("Action Items Agent starting...")

    print("Authenticating with Google...")
    credentials = get_google_credentials()

    print("Fetching today's Fathom action items...")
    fathom_data = get_todays_action_items(user_email)
    print(
        f"  Fathom: {fathom_data['meetings_checked']} meeting(s) | "
        f"{len(fathom_data['mine'])} mine, {len(fathom_data['others'])} others"
    )

    print("Fetching Notion action items...")
    notion_data = get_all_action_items()
    print(
        f"  Notion: {len(notion_data['mine'])} mine, {len(notion_data['others'])} others"
    )

    print("Synthesizing digest with Claude...")
    digest_html = synthesize_action_items(fathom_data, notion_data, today_date)
    full_html = _build_html_wrapper(digest_html, today_date)

    print(f"Sending email to {recipient}...")
    _send_email(credentials, recipient, full_html, today_date)
    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
