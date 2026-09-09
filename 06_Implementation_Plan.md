# Implementation Plan — ResolveIQ (finish by the weekend)

Rule for the whole plan: Feature 1 (drafting + feedback loop) is built deep
and fully working. Features 2-4 are deliberately light additions riding on
Feature 1's shared data layer — not separate systems. If time runs short, the
cut order is fixed: **Feature 4 first, then Feature 3. Never cut Feature 1 or 2.**

## Day 1 (Mon) — Foundation, shared by all four features
- [ ] Postgres schema (05_Backend_Schema.md), migrations
- [ ] FastAPI scaffold, health check
- [ ] Auth: login, password hashing, JWT access + refresh, role check middleware
- [ ] Next.js scaffold: login page, empty queue page (mock data)
- [ ] Ticket submission endpoint (status=`new`) — no AI yet
- [ ] Checkpoint: explain the auth flow out loud, no notes

## Day 2 (Tue) — Feature 1, part A
- [ ] Download/prepare urgency+category training data (Kaggle ticket dataset
  + hand-written fintech examples); train the classifier
- [ ] PII redaction pass (regex + simple NER)
- [ ] Write ~15-25 KB articles; embed into pgvector
- [ ] Retrieval agent: top-k, category-filtered search
- [ ] Checkpoint: explain why a trained classifier instead of an LLM call

## Day 3 (Wed) — Feature 1, part B
- [ ] Drafting agent: grounded reply + citations + confidence, stronger model
- [ ] LangGraph wiring: classify → retrieve → draft → decide, as a Celery task
- [ ] Retry/timeout/fallback handling on LLM and embedding calls
- [ ] Prompts written as versioned functions/files, not inline strings

## Day 4 (Thu) — Feature 1 end-to-end + Feature 2
- [ ] Frontend: queue view + ticket detail (draft, sources, confidence)
- [ ] Approve / edit / escalate actions wired to `ticket_resolutions`
- [ ] Correction capture on edit → `correction_signals` → retrieval_boost update
- [ ] Feature 2: `customer_id` join, customer-history summary injected into
  the drafting agent's prompt
- [ ] Checkpoint: run the "correction improves next draft" sequence end to end

## Day 5 (Fri) — Feature 3 + Feature 4 (kept light)
- [ ] Feature 3: synthetic breach-risk labeling rule + small classifier;
  queue view reordered by breach-risk score
- [ ] Feature 4: coaching view aggregating edit-distance, resolution time,
  escalation rate per agent — reporting only, no new backend logic
- [ ] Audit log written on every state transition; basic admin audit view

## Day 6 (Sat) — Buffer, hardening, demo prep — not new features
- [ ] Langfuse tracing across the full pipeline
- [ ] One RAGAS eval run for real retrieval-quality numbers
- [ ] Rate limiting, CORS lockdown, secrets in env vars
- [ ] Docker Compose: api, worker, postgres, redis, frontend
- [ ] README: architecture summary + the production-technique table (from TRD)
- [ ] Rehearse demo: pre-seeded tickets + one live-typed ticket +
  correction-improves-next-draft sequence

## Cut list if time runs out (in this order)
1. Feature 4 (coaching insights) — drop the view, keep the underlying data capture
2. Feature 3 (SLA prioritization) — fall back to urgency-only queue sort
3. RAGAS eval numbers — mention as "planned" if genuinely out of time
4. Full audit log UI — keep the data captured, skip the polished view
Never cut: the Feature 1 end-to-end loop, auth, PII redaction, or the
correction → retrieval feedback mechanism. Those are the whole point of the
project and what you'll be asked to defend in detail.
