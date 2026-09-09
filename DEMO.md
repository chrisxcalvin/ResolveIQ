# Demo runbook

Prereqs: KB embedded, both classifiers trained, LoRA adapter fine-tuned (see
README's "Seeding & training"), then:

```bash
cd backend && uv run python -m app.scripts.seed_demo
```

Log in at the frontend with `demo@resolveiq.io` / `resolveiq-demo` (printed
by the seed script). This account has the `admin` role, so it can do
everything an agent can plus see the coaching/audit-log views.

## 1. Queue view — breach-risk prioritization (Feature 3)

Open `/queue`. Point out:
- The seeded tickets are sorted by breach-risk score, not raw urgency —
  the fraud-flavored dispute ticket for the returning customer should sort
  near the top even though other tickets may have comparable urgency,
  because category + queue depth push its breach-risk score up.
- The urgency/breach-risk badges, and that a ticket with no score yet
  (still processing) falls back to urgency-only sort — the documented
  failure-path behavior, not a bug.

## 2. Ticket detail — grounded draft + customer history (Features 1 & 2)

Click into the returning customer's dispute ticket. Point out:
- **Customer history** panel — their 2 prior resolved tickets, which were
  injected as context into the drafting prompt (Feature 2). This is *why*
  the model has enough to work with even though the ticket is short.
- **AI draft reply** — grounded, cites specific KB sources (expand a
  source to show the actual chunk text it's grounded in), with a numeric
  confidence score, not a self-reported one.
- **Sources** — click to expand, show the retrieved chunk content lines up
  with what's actually in the reply.

## 3. Live-typed ticket

Go back to submitting a new ticket (via `POST /tickets` — either through
`/docs` or a submission form if wired up) with a message similar to one
already in the KB, e.g.:

> "My payment failed but I can still see the charge pending on my
> statement, was I actually charged?"

Watch it land in the queue as `new`, then move to `drafted` within a few
seconds once the worker picks it up. Open it — grounded draft, cited
sources, confidence score, same as the seeded ones. This proves the
pipeline works live, not just on canned data.

## 4. Correction improves next draft — the core mechanic

This is the one to slow down for.

1. On a **drafted** ticket, click **Edit then send**, meaningfully rewrite
   the reply (not a one-word tweak — the demo should show a real
   correction), and submit.
2. Open the admin audit log (`/admin/audit-log`) — show the `edit` event
   with its full reasoning snapshot (category, confidence, sources,
   `edit_distance`).
3. In a terminal, show the mechanism directly:
   ```bash
   cd backend
   uv run python -m app.retrieval.retrieve "<similar query to the edited ticket>" <category>
   ```
   Run it once before the edit (if rehearsing, capture this first) and
   once after — the corrected-against chunk(s) rank lower (or drop out of
   the top-k entirely), because `retrieval_boost` was demoted on edit
   (`app/retrieval/retrieve.py::adjust_retrieval_boost`).
4. Submit a **new**, similar ticket live. Its draft should now lean on
   different (better) source chunks than the one that got corrected —
   that's the loop closing, live, not a canned example.

## 5. Coaching + audit trail (Feature 4 + hardening)

- `/admin/coaching` — edit-distance, resolution time, escalation rate for
  the demo account, aggregated from data already captured, no new backend
  logic.
- `/admin/audit-log` — every state transition (submitted, drafted,
  approve/edit/escalate) with full reasoning data, admin-only.

## 6. If asked "does this actually work in production shape"

- `uv run python -m app.eval.ragas_eval` — real retrieval-quality numbers
  (not eyeballed), runs in seconds, no LLM judge needed.
- Point at `app/core/tracing.py` — Langfuse traces every pipeline step and
  LLM/embedding call when `LANGFUSE_PUBLIC_KEY`/`SECRET_KEY` are set; ask to
  see a trace live if Langfuse is configured for the demo environment.
- `docker compose up --build` — the whole stack (api, worker, postgres,
  redis, frontend) from one command.
