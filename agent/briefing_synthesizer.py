import json
import os

import anthropic

PRE_MEETING_PROMPT = """You are a personal chief of staff preparing a busy advisor for their next meeting. You receive the meeting details, relevant email history, and Notion notes. Produce a concise, high-value pre-meeting briefing the advisor can read in under 3 minutes.

SECTIONS TO ALWAYS INCLUDE:

1. MEETING SNAPSHOT
   - Who is attending (name, company/role if known)
   - Purpose of the meeting in one sentence
   - Location or video link
   - Duration

2. BACKGROUND & CONTEXT
   - Who are these people and what is the relationship history?
   - What project, deal, or topic does this meeting concern?
   - Anything important that happened recently with this person/topic?

3. RELEVANT EMAIL THREADS
   - Summarize the most important recent email conversations.
   - Highlight open questions, commitments made, or unresolved items.
   - If no emails: say "No recent email history found."

4. NOTES & PREVIOUS MEETINGS
   - Summarize any relevant Notion pages (previous meeting notes, project docs, decisions).
   - Call out any open action items from prior meetings.
   - If no Notion pages: say "No prior meeting notes found."

5. OPEN ACTION ITEMS & QUESTIONS
   - What is each party responsible for from previous interactions?
   - What questions must the advisor get answered in this meeting?

6. SUGGESTED TALKING POINTS
   - 3-5 bullet points: what to cover, what to achieve, what to watch out for.

OUTPUT FORMAT:
Return a valid HTML fragment only. No <html>/<head>/<body> tags. Inline styles only.

<h2 style="margin:0 0 4px;font-size:18px;color:#1a1a2e;">{Meeting Title}</h2>
<p style="margin:0 0 20px;color:#718096;font-size:14px;">{time} &middot; {duration} &middot; {location or video link or 'No location set'}</p>

<h3 style="margin:20px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;color:#718096;">Attendees</h3>
<ul style="margin:0;padding-left:20px;">
  <li style="margin-bottom:4px;">{Name} &mdash; {role/company if known}</li>
</ul>

<h3 style="margin:20px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;color:#718096;">Background & Context</h3>
<p style="margin:0;">{2-4 sentences of context}</p>

<h3 style="margin:20px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;color:#718096;">Relevant Email Threads</h3>
<ul style="margin:0;padding-left:20px;">
  <li style="margin-bottom:8px;"><strong>{Subject}</strong> ({date}) &mdash; {one sentence summary of what matters}</li>
</ul>

<h3 style="margin:20px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;color:#718096;">Notes & Previous Meetings</h3>
<ul style="margin:0;padding-left:20px;">
  <li style="margin-bottom:8px;"><strong>{Page title}</strong> (last edited {date}) &mdash; {key takeaway}</li>
</ul>

<h3 style="margin:20px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;color:#718096;">Open Action Items & Questions</h3>
<ul style="margin:0;padding-left:20px;">
  <li style="margin-bottom:6px;">{action item or question}</li>
</ul>

<h3 style="margin:20px 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:0.8px;color:#718096;">Suggested Talking Points</h3>
<ul style="margin:0;padding-left:20px;">
  <li style="margin-bottom:6px;">{talking point}</li>
</ul>

Be specific and direct. Maximum 600 words. Never leave a section empty - always write something useful."""


def synthesize_pre_meeting_briefing(meeting: dict, research: dict) -> str:
    """Call Claude to produce the pre-meeting HTML briefing."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    model = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

    user_message = f"""MEETING DETAILS:
{json.dumps(meeting, indent=2)}

RELEVANT EMAILS ({len(research['emails'])} found, most recent first):
{json.dumps(research['emails'], indent=2) if research['emails'] else '(none found)'}

RELEVANT NOTION PAGES ({len(research['notion_pages'])} found):
{json.dumps(research['notion_pages'], indent=2) if research['notion_pages'] else '(none found)'}

Generate the pre-meeting briefing HTML now."""

    response = client.messages.create(
        model=model,
        max_tokens=1400,
        system=[
            {
                "type": "text",
                "text": PRE_MEETING_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text
