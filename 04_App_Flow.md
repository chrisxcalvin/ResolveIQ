# App Flow — ResolveIQ

## 1. Ticket lifecycle (primary flow — Feature 1, core)

1. **Ticket submitted** — via API endpoint (simulating email/chat/form
   intake). Stored in Postgres, status `new`. Background job enqueued
   (Celery) — API returns immediately.
2. **Classify + retrieve** (async worker, multi-agent):
   a. PII redaction pass on raw ticket text.
   b. Classification agent: structured-output urgency score + category
      (trained classifier).
   c. Retrieval agent: embeds the redacted query, retrieves top-k relevant
      chunks from pgvector (KB docs + past resolved tickets), filtered by
      category, boosted by prior correction signals.
3. **Customer context pulled in (Feature 2)** — tickets joined by
   `customer_id`; a short summary of the customer's history across channels
   is added to the drafting agent's context.
4. **Agent drafts reply** — drafting agent (stronger model) generates a
   grounded reply + confidence + cited sources. Status → `drafted`.
5. **Queue reprioritized (Feature 3)** — breach-risk model scores the ticket
   against age/category/queue-depth; queue view reorders by this score.
6. **Human reviews** — agent opens ticket detail, sees draft, urgency,
   breach-risk, customer context, sources.
   - **Approve & send** → status `resolved`.
   - **Edit then send** → diff captured as a correction signal tied to the
     sources used; status `resolved`.
   - **Escalate** → status `escalated`, routed with agent's note.
7. **Feedback loop** — correction signals adjust retrieval ranking (boost
   sources tied to good outcomes, demote ones tied to frequent corrections).
8. **Coaching data updates (Feature 4)** — edit-distance, resolution time,
   and escalation events roll up into the per-agent coaching view.
9. **Audit trail** — every state transition logged with its reasoning data,
   queryable by admins.

## 2. Secondary flow — knowledge base update
1. Admin uploads a new help doc.
2. Backend chunks and embeds it into pgvector.
3. Doc becomes eligible for retrieval on the next matching ticket.

## 3. Secondary flow — authentication
1. User submits email/password.
2. Backend verifies hash, issues short-lived access token + refresh token.
3. Refresh token (rotated each use) issues a new access token without re-login.
4. Role (`agent`/`admin`) embedded in token claims, checked on protected routes.

## 4. Failure paths to handle
- LLM/embedding service down → ticket stays queued, flagged for manual
  handling, retried with backoff.
- Classifier confidence very low → default to a safe middle urgency rather
  than guessing high or low.
- Retrieval returns nothing relevant → draft explicitly says so, never
  fabricates an answer.
- Breach-risk model unavailable → queue falls back to urgency-only sort.
