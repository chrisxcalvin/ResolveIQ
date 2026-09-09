# Product Requirements Document — ResolveIQ

## 1. Problem statement
Fintech support teams (payments, wallets, lending apps) face four compounding
problems: (1) agents spend most of their time manually judging urgency and
searching docs before they can even start helping, causing slow, inconsistent
replies; (2) customers repeat themselves across email/chat/social because
context isn't shared across channels; (3) genuinely urgent tickets (possible
fraud, high-value disputes) get buried in the queue behind routine ones and
miss SLAs; (4) agents get no structured feedback on their own performance over
time. Existing AI support tools address replies but treat every human
correction as a one-off fix, discarding a signal that could make the system
better over time.

## 2. Solution summary — four features, one shared platform
A human-in-the-loop AI copilot for support agents (not a customer-facing bot),
built as one platform with four features sharing the same data and agent layer:

1. **Grounded reply drafting** — trained urgency/category classifier + RAG
   agent + drafting agent produce a grounded, cited draft; a human always
   approves, edits, or escalates. Corrections feed back into retrieval ranking
   so replies measurably improve over time. *(Deep-built, centerpiece feature.)*
2. **Cross-channel customer context** — tickets linked by customer ID; a
   summary of the customer's history is pulled into the draft prompt so no
   agent starts from zero. *(Light feature, reuses Feature 1's infrastructure.)*
3. **SLA breach-risk prioritization** — a simple trained model reorders the
   queue by breach likelihood (ticket age, category, queue depth) instead of
   raw urgency alone. *(Light feature.)*
4. **Agent coaching insights** — a reporting view surfacing patterns already
   captured by the system: edit-distance on drafts, resolution time, escalation
   rate per agent. *(Light feature, no new backend logic — reporting only.)*

## 3. Users
- **Primary**: support agent — reviews queue, approves/edits/escalates drafts.
- **Secondary**: support admin/lead — manages KB content, views audit logs and
  coaching insights.
- **Not a user**: the end customer — never interacts with this system directly.

## 4. Goals / success criteria
- Ticket goes from submission to reviewable draft in seconds (async processing).
- Urgency classifier separates high-stakes tickets from routine ones with a
  measurable accuracy on a held-out test set.
- After human corrections on a topic, a similar new ticket's draft
  demonstrably improves — reproducible in a live demo.
- Queue reordered by breach-risk visibly surfaces at-risk tickets earlier than
  a naive FIFO/urgency-only ordering.
- Every automated decision (score, sources, routing) has a stored reason —
  zero silent decisions.

## 5. Non-goals (explicitly out of scope)
- No customer-facing chatbot or live chat widget.
- No voice/call transcription.
- No fully autonomous auto-send for high-risk categories (fraud, large
  refunds) — these always route to a human.
- No multi-tenant support — single organization only.
- No fine-tuning of large frontier models — the drafting agent's cheap-tier
  model is a small (≤1B parameter) open-weight model LoRA-fine-tuned locally
  for routine/low-risk replies; the stronger tier remains a prompted LLM.
  Classification stays a small trained classifier (not fine-tuned), and
  retrieval stays retrieval — no fine-tuning there.
- No real-time SLA forecasting — a simple, honestly-synthetic breach-risk
  score, not production-grade time-series forecasting.

## 6. Timeline
Build-to-demo window: **this week, finishing by the weekend.** Feature 1 is
non-negotiable and fully built; Features 2-4 are intentionally light additions
riding on Feature 1's infrastructure. See Implementation Plan for the exact
day-by-day breakdown and cut order if time runs short.

## 7. Key risks
- Tight timeline — mitigated by building the deep feature first, light
  features only once it's solid, and a fixed cut order (4 → 3 → never 1 or 2).
- "AI support triage" is a saturated market category — differentiation rests
  on the live feedback-loop mechanic in Feature 1, not the base pattern.
- PII in tickets (names, account numbers, transaction IDs) — mitigated by
  redaction before logging/LLM calls (see TRD, security section).
- No real fintech ticket dataset exists publicly — mitigated by using a
  general public ticket dataset plus a small set of hand-written fintech
  examples (see App Flow / dataset notes in TRD).
