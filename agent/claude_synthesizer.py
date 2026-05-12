import json
import os

import anthropic

SYSTEM_PROMPT = """You are a personal chief of staff for a busy advisor. Every morning you receive their calendar events, Notion tasks, and unanswered emails, then produce a concise, actionable morning briefing.

INSTRUCTIONS:
1. Rank TODAY's items by: (a) hard deadlines and fixed meeting times, (b) strategic importance to the business, (c) estimated energy/effort cost.
2. Flag any TOMORROW items that require preparation today.
3. Identify at least one time gap today suitable for focused deep work.
4. For each unanswered email, note how many days it has been waiting and flag those over 2 days as overdue.
5. If there are no calendar events or tasks, produce an encouraging "light day" message and suggest proactive work.

OUTPUT FORMAT:
Return a valid HTML fragment only - no <html>, <head>, or <body> tags. Use inline styles exclusively.
Structure:
  <h2> "Today - {weekday, date}"
  <p> One-sentence overview of the day's theme or energy level
  <h3>Priorities</h3>  (numbered list <ol>)
  <h3>Tomorrow Preview</h3>  (bullet list <ul>; skip if tomorrow is empty)
  <h3>Unanswered Emails</h3>  (bullet list with sender, subject, age; skip if none)
  <h3>Suggested Focus Block</h3>  (one paragraph)

Style rules:
  - Font: inherit (email client will apply it)
  - Priority items: use <strong> for the title, plain text for context
  - Overdue emails (>2 days): wrap age in <span style="color:#e53e3e;font-weight:600;">
  - Section headings <h3>: style="margin:20px 0 8px;font-size:14px;text-transform:uppercase;letter-spacing:0.8px;color:#718096;"
  - Keep total length under 500 words."""


def synthesize_priorities(
    calendar_data: dict,
    notion_data: dict,
    unanswered_emails: list[dict],
) -> str:
    """Call Claude to produce the HTML digest from the combined data."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    user_message = f"""Date: {calendar_data['today_date']}
Current time: {calendar_data['current_time']}
Timezone: {os.environ.get('USER_TIMEZONE', 'America/Chicago')}

CALENDAR - TODAY ({calendar_data['today_date']}):
{json.dumps(calendar_data['today'], indent=2) if calendar_data['today'] else '(no events)'}

CALENDAR - TOMORROW ({calendar_data['tomorrow_date']}):
{json.dumps(calendar_data['tomorrow'], indent=2) if calendar_data['tomorrow'] else '(no events)'}

NOTION TASKS - TODAY:
{json.dumps(notion_data['today'], indent=2) if notion_data['today'] else '(none)'}

NOTION TASKS - TOMORROW:
{json.dumps(notion_data['tomorrow'], indent=2) if notion_data['tomorrow'] else '(none)'}

UNANSWERED EMAILS (last 7 days, oldest first):
{json.dumps(unanswered_emails, indent=2) if unanswered_emails else '(none)'}

Generate the morning briefing HTML now."""

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text
