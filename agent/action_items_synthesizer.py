import json
import os

import anthropic

SYSTEM_PROMPT = """You are a personal chief of staff for Fidel Salazar at Fidaris Advisory. Every evening at 6 PM you compile an action-items digest from Fathom meeting recordings and Notion trackers.

INSTRUCTIONS:

1. MY ACTION ITEMS — items where Fidel is the owner
   - Group by project/client (CEMEX, CFP, AI Trainings, Syncron/O2C, LSU, Other)
   - Within each group, list items concisely — one line per item
   - Prefix each with a status icon: 🔴 BLOCKED | 🟡 IN PROGRESS | ⬜ Not Started
   - Append the source context in parentheses (meeting title or tracker name)

2. OTHERS' ACTION ITEMS — items assigned to other people
   - Group by project/client
   - Show the assignee name in bold before each item
   - Flag items where someone owes Fidel something (call-outs, materials to send, follow-ups)
   - Same status icons as above

STYLE:
- Be concise — one line per item
- No padding, no filler sentences
- Skip items with no task text

OUTPUT: Valid HTML fragment, no <html>/<head>/<body> tags, inline styles only.

Use this template structure:

<h3 style="margin:20px 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.8px;color:#718096;">✅ My Action Items</h3>

<p style="margin:12px 0 4px;font-weight:600;color:#2d3748;">🏗️ CEMEX</p>
<ul style="margin:0 0 12px;padding-left:20px;">
  <li style="margin-bottom:5px;">⬜ Item text <span style="color:#718096;font-size:13px;">(source)</span></li>
</ul>

<h3 style="margin:20px 0 6px;font-size:12px;text-transform:uppercase;letter-spacing:.8px;color:#718096;">👥 Others' Action Items</h3>

<p style="margin:12px 0 4px;font-weight:600;color:#2d3748;">🏗️ CEMEX</p>
<ul style="margin:0 0 12px;padding-left:20px;">
  <li style="margin-bottom:5px;"><strong>Assignee Name:</strong> ⬜ Item text <span style="color:#718096;font-size:13px;">(source)</span></li>
</ul>

Max 900 words."""


def synthesize_action_items(
    fathom_data: dict,
    notion_data: dict,
    today_date: str,
) -> str:
    """Call Claude to produce the HTML action-items digest."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    all_mine = notion_data.get("mine", []) + fathom_data.get("mine", [])
    all_others = notion_data.get("others", []) + fathom_data.get("others", [])

    user_message = (
        f"Date: {today_date}\n"
        f"Fathom meetings checked today: {fathom_data.get('meetings_checked', 0)}\n\n"
        f"MY ACTION ITEMS ({len(all_mine)} open):\n"
        f"{json.dumps(all_mine, indent=2) if all_mine else '(none)'}\n\n"
        f"OTHERS' ACTION ITEMS ({len(all_others)} open):\n"
        f"{json.dumps(all_others, indent=2) if all_others else '(none)'}\n\n"
        "Produce the evening digest. Group by project, one line per item, status icons."
    )

    response = client.messages.create(
        model=model,
        max_tokens=1800,
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
