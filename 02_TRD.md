# Technical Requirements Document — ResolveIQ

## 1. Tech stack and why

| Layer | Choice | Why (interview-ready reasoning) |
|---|---|---|
| Frontend | Next.js | SSR for fast dashboard load, simple routing for a small internal tool |
| Backend API | FastAPI | Async-native, automatic OpenAPI docs, Pydantic validation |
| Database | PostgreSQL | Relational integrity for tickets/users/roles; mature transactions |
| Vector store | pgvector (inside Postgres) | Avoids a second database just for embeddings; keeps ticket and vector data transactionally consistent |
| Agent orchestration | LangGraph | Explicit multi-agent state machine instead of one big prompt; each step inspectable/testable independently |
| Async/queue | Celery + Redis | Ticket processing must not block the API request; retry/backoff for LLM/embedding failures |
| Auth | JWT (access + refresh) | Stateless verification; refresh rotation limits stolen-token damage |
| Observability | Langfuse | Traces every agent step — prompt, tokens, latency, cost |
| Eval | RAGAS | Real numbers for retrieval quality, not a vibe |
| Containerization | Docker Compose | One-command local spin-up of api + worker + db + redis + frontend |

## 2. Multi-agent architecture (LangGraph)
Four distinct agent nodes, not one prompt:
1. **Classification agent** — structured/schema-validated output: category +
   urgency score, from a small trained classifier (not an LLM guess).
2. **Retrieval agent** — queries pgvector for relevant KB chunks + past
   resolved tickets, filtered/boosted by category and by prior correction signals.
3. **Drafting agent** — generates a grounded reply citing the sources it used,
   with a confidence score. Internally model-routed: a small (≤1B param)
   open-weight model LoRA-fine-tuned on grounded fintech support replies
   handles routine/low-risk categories; a stronger prompted LLM handles
   harder or high-urgency ones. Both tiers cite sources and produce a
   confidence score the same way.
4. **Decision/escalation agent** — given confidence + urgency + category,
   decides: route for review, or route to specialist escalation. Never
   auto-sends high-risk categories.

State is passed between nodes explicitly; the graph can branch depending on
the decision agent's output rather than always running a fixed sequence.

## 3. Production LLM techniques deliberately built in

| Technique | Where it lives | Why it matters in industry |
|---|---|---|
| Structured output / function calling | Classification agent returns schema-validated JSON | Prevents downstream parsing breakage |
| Grounding + citations | Drafting agent always cites source chunks | Directly addresses hallucination — the top RAG interview question |
| Prompt templating/versioning | Prompts as versioned functions/files, not hardcoded strings | Real teams treat prompts like code |
| Model routing | Small trained classifier for classification; within drafting, a LoRA-fine-tuned small model for routine tickets vs. a stronger prompted LLM for harder ones | Standard cost-optimization pattern, now with a real fine-tuned model on the cheap tier instead of just "a smaller API model" |
| Retry + timeout + fallback | LLM/embedding calls wrapped with backoff; falls back to "needs manual response" | Production systems never assume the call always succeeds |
| Guardrails (PII redaction) | Redaction pass before any text hits an LLM or gets logged | Real compliance requirement |
| Observability/tracing | Langfuse on every agent step | How real teams debug and cost-monitor LLM pipelines |
| Automated evaluation | RAGAS run as a script | Shows evaluation isn't just eyeballing outputs |
| Feedback loop | Correction signals re-rank retrieval | The project's one differentiating mechanic |

## 4. Datasets

- **Urgency/category classifier**: public Kaggle ticket datasets with
  priority/department labels (e.g. multilingual customer support ticket
  dataset, or a dedicated support-ticket-priority dataset) mapped onto this
  project's urgency scale. Supplemented with ~50-100 hand-written or
  LLM-drafted fintech-flavored examples (failed payment, refund delay,
  locked account, disputed transaction) since no public fintech ticket
  dataset exists.
- **Knowledge base (RAG corpus)**: self-written, not scraped. 15-25 short
  mock help articles covering the ticket categories in scope, written by hand
  or drafted with an LLM from bullet points. Avoids copyright/ToS issues from
  scraping a real company's help center.
- **SLA breach-risk model**: synthetic. Auto-labeled from ticket age,
  category, urgency, and queue depth using a simple rule, then a small
  classifier trained on that synthetic label. Explicitly not real breach data
  — framed honestly as a demonstration of the mechanism, not a real pattern.
- **Feedback/correction data**: generated live during testing/demo — no
  dataset needed, created by acting as both "customer" and "reviewing agent."

## 5. Security requirements
- Password hashing: bcrypt or argon2, never plaintext/reversible.
- JWT access tokens short-lived; refresh tokens rotated and revocable.
- RBAC (`agent` vs `admin`) enforced at the API layer, not just the UI.
- PII redaction (account numbers, emails, phone numbers) before any LLM call
  or log write.
- Rate limiting on the API gateway.
- Secrets in environment variables only.
- CORS locked to the known frontend origin.

## 6. Non-functional requirements
- Ticket processing is async — API returns immediately, worker runs the pipeline.
- Every automated decision is persisted with enough detail to reconstruct "why."
- Graceful degradation if the LLM/embedding service is unavailable — ticket
  queues and flags for manual handling rather than silently failing.
