import json
import os

import anthropic

SYSTEM_PROMPT = """You are a personal chief of staff for a busy advisor at Fidaris Advisory. Every morning you receive their calendar events, Notion tasks, unanswered emails, and produce a structured morning briefing.

INSTRUCTIONS:

1. CALENDAR PRIORITIES
   - List today's events/tasks in order of: (a) fixed meeting times, (b) hard deadlines, (c) strategic importance.
   - For each item, add one sentence of context on what to focus on or watch out for.

2. EMAILS REQUIRING IMMEDIATE ACTION
   - From the unanswered emails list, identify those that clearly require a response or decision (not newsletters, automated emails, or FYIs).
   - Flag any that are overdue (waiting more than 2 days) in red.
   - For each, write one sentence on what action is needed (reply, approve, follow up, etc.).

3. MEETING PREP ALERTS
   - Review ALL meetings on today's and tomorrow's calendar.
   - For each meeting that requires preparation (trainings, client presentations, workshops, strategy sessions, demos — anything where showing up unprepared would be a problem), check if there is a preparation or prep block scheduled in the calendar at least 24 hours before that meeting.
   - If NO prep block exists: flag it with a warning and suggest a specific time window today to prepare.
   - If a prep block EXISTS: briefly confirm it.
   - Rule of thumb: any meeting with words like "training", "workshop", "presentation", "demo", "client", "pitch", "review", "interview" likely needs prep.

4. SUGGESTED FOCUS BLOCK
   - Identify the best open time window today for deep, focused work (no meetings, good energy time).
   - Suggest what to work on during that block based on the day's priorities.

OUTPUT FORMAT:
Return a valid HTML fragment only - no <html>, <head>, or <body> tags. Use inline styles exclusively.

Use this exact structure:

<h2 style="margin:0 0 4px;font-size:18px;color:#1a1a2e;">Today - {weekday, date}</h2>
<p style="margin:0 0 20px;color:#718096;font-size:14px;">{One sentence: overall energy/theme of the day}</p>

<h3 style="margin:20px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;color:#718096;">Calendar Priorities</h3>
<ol style="margin:0;padding-left:20px;">
  <li style="margin-bottom:10px;"><strong>{Event title, time}</strong> - {one sentence context}</li>
</ol>

<h3 style="margin:20px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;color:#718096;">Emails Requiring Action</h3>
<ul style="margin:0;padding-left:20px;">
  <li style="margin-bottom:10px;">
    <strong>{Sender}</strong>: {Subject} <span style="color:#718096;font-size:13px;">({age} days ago)</span> - {what action is needed}
    <!-- If overdue >2 days: wrap the age in <span style="color:#e53e3e;font-weight:600;"> -->
  </li>
</ul>
<!-- If no actionable emails: <p style="color:#718096;font-size:14px;">No emails requiring immediate action.</p> -->

<h3 style="margin:20px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;color:#718096;">Meeting Prep Alerts</h3>
<ul style="margin:0;padding-left:20px;">
  <li style="margin-bottom:10px;">
    <!-- WARNING - no prep block found: -->
    <span style="color:#d97706;font-weight:600;">&#9888; {Meeting title} ({date, time})</span> - No prep block found. Suggested prep window: {specific time today, e.g. 2:00-3:00 PM}.
    <!-- OR if prep block exists: -->
    <span style="color:#38a169;font-weight:600;">&#10003; {Meeting title}</span> - Prep block scheduled {date/time}.
  </li>
</ul>
<!-- If no meetings need prep: <p style="color:#718096;font-size:14px;">No meetings requiring preparation in the next 24 hours.</p> -->

<h3 style="margin:20px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;color:#718096;">Suggested Focus Block</h3>
<p style="margin:0;">{Best open window today} - {what to work on and why}</p>

KEEP total length under 550 words. Be direct and specific - no filler phrases."""


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

Generate the morning briefing HTML now. Pay special attention to the Meeting Prep Alerts section - scan every meeting on today's and tomorrow's calendar and flag any that need preparation but have no prep block scheduled."""

    response = client.messages.create(
        model=model,
        max_tokens=1200,
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
