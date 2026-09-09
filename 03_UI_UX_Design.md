# UI/UX Design — ResolveIQ

Audience: internal support agents and admins. Not customer-facing. Prioritize
clarity and speed over visual polish.

## 1. Login screen
- Email + password, error state for invalid credentials.
- No public sign-up — accounts are admin-provisioned.

## 2. Ticket queue (agent's home screen) — Features 1 & 3
- List of open tickets, **default sorted by SLA breach-risk score**, not raw
  urgency alone (Feature 3).
- Each row: ticket ID, masked customer identifier, category tag, urgency
  badge (color-coded), breach-risk indicator, time since submission, status.
- Filter bar: by category, urgency, status.
- "Queue health" strip: counts by urgency/breach-risk band.

## 3. Ticket detail view — Features 1 & 2
- Left panel: original message (PII-masked in display), plus a **customer
  context summary** pulled from their history across channels (Feature 2) —
  e.g. "3 prior tickets, last: refund delay, resolved 2 weeks ago."
- Right panel: AI draft with confidence score, "grounded in" source citations,
  urgency/category with a one-line reason.
- Action bar: **Approve & send**, **Edit then send**, **Escalate**.
- Editing captures the diff silently for the feedback loop — no extra agent
  action needed.
- Escalating: pick specialist/team + optional note.

## 4. Audit log view (admin only) — Feature 1
- Searchable table: ticket ID, decision, urgency score, sources used, acting
  agent, timestamp. Click into a row for the full reasoning trail.

## 5. Coaching insights view (admin, and agents for their own stats) — Feature 4
- Per-agent summary: average edit-distance on drafts (how much they change AI
  drafts), average resolution time, escalation rate.
- Trend view: are these improving over time as the system's drafts improve too.
- Framed as a working aid, not a performance-review tool — described plainly
  as pattern surfacing, not scoring/ranking agents against each other.

## 6. Knowledge base management (admin only)
- List of uploaded docs; upload triggers re-embedding into pgvector.
- Simple view of which docs get retrieved most often / most corrected against.

## 7. States to design for
- Empty queue ("all caught up").
- AI processing pending (don't block the agent from working other tickets).
- Model/LLM unavailable — ticket flagged "AI draft unavailable, manual
  response needed," never silently stuck.

## 8. Visual conventions
- Urgency color coding: red = high, amber = medium, gray = low/routine.
- Breach-risk shown as a separate, clearly distinct indicator from urgency —
  they can disagree (e.g. medium urgency, high breach-risk due to queue depth).
- Confidence and source citations visible by default, not hidden behind a click.
