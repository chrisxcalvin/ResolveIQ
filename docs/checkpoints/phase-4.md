# Phase 4 checkpoint — database migration off WSL2

## What did you actually build?

Moved Postgres+pgvector and Redis off the WSL2-hosted local setup onto
Neon and Upstash — both serverless, both free-tier, both externally
reachable. Verified this wasn't just "the app didn't crash": ran the
existing 2 Alembic migrations against a completely empty Neon database
(never tested from empty before — every prior run was incremental against
the already-set-up WSL2 database), confirmed all 9 tables landed correctly,
re-embedded the 20-article knowledge base into Neon (60 chunks, matching
the local count exactly), seeded the demo user and ran 4 real tickets
through the full pipeline against the cloud stack, then submitted one more
live ticket end-to-end through the actually-running API/worker — correctly
redacted, classified, retrieved, drafted, with a working Groq call.

## Why this approach, and what else did you consider?

For the database, the alternative worth naming is Supabase — it bundles
auth and storage alongside Postgres, which this project doesn't need
(auth is already hand-rolled with JWT). Neon is the more direct swap for
"plain Postgres+pgvector, hosted," plus branching, which is a genuinely
useful thing to have for testing a migration against an isolated copy
before running it against the real database — not used yet in this phase,
but the reason Neon specifically over a generic "any hosted Postgres."

For Redis, the alternative was a plain Redis Cloud/self-managed instance.
Upstash's specific advantage is that it's built for exactly this shape of
workload (Celery broker traffic, not sustained high-throughput caching) and
pairs with a serverless Postgres choice without needing a persistent
server to manage on either side.

The other real decision this phase: you handed me a copy-pasted Neon
onboarding flow that included `neon mcp -y` — installing an MCP server
that would give me standing, direct access to create/delete your Neon
projects and run arbitrary SQL, in this and future sessions, not just a
one-time setup command. I stopped and explained that capability
explicitly before running anything, rather than treating `-y` as "safe
because it was in the instructions." You chose the plain connection-string
path instead once you saw what the MCP option actually granted. Worth
recording here because it's a real example of the tradeoff this project's
own decision agent embodies elsewhere: convenience/automation versus a
human actually seeing what they're approving.

## What's the failure mode if this were wrong or missing?

Two distinct ones surfaced during the actual cutover, not hypothetically:

1. **Celery's `rediss://` requirement.** The worker crashed on startup
   with `A rediss:// URL must have parameter ssl_cert_reqs...` — Celery's
   redis backend refuses to start on a TLS Redis URL without an explicit
   certificate-verification mode. Upstash's own dashboard doesn't show you
   this; you only find out by actually starting the worker. Fixed by
   appending `?ssl_cert_reqs=CERT_REQUIRED` to `REDIS_URL`. If missed, the
   worker never starts at all — loud and immediate, not a silent one.
2. **Stale running processes.** After fixing `.env`, I restarted the
   Celery worker but not the API — and the API crashed with the *same*
   `rediss://` error the moment a ticket was submitted, because
   `pydantic-settings` reads `.env` once at process startup, and the API
   process was still holding the old, broken Redis config in memory. Both
   processes need a restart after any `.env` change, not just the one you
   assume is affected — an easy thing to get half-right.

## What's the one follow-up question a sharp interviewer would ask next, and what's the honest answer?

*"Why Postgres+pgvector instead of a dedicated vector database like
Pinecone or Weaviate?"* — Because the actual query this system runs is
never "vector search alone" — it's always vector search filtered by
category, joined against `kb_documents` for the title, and read alongside
`retrieval_boost` for the feedback loop, in the same transaction as
writing `times_retrieved`. That's a relational query with a vector
component, not a pure nearest-neighbor lookup, and keeping it in one
engine means one connection, one transaction, one consistency model,
instead of syncing two databases and hoping they agree. A dedicated
vector DB earns its cost at a scale and query pattern this project doesn't
have — dozens of thousands to millions of vectors, pure similarity search
as the dominant workload. At 60 chunks, that tradeoff doesn't apply yet.

**The harder, more honest part of that answer**, found while writing this
checkpoint rather than assumed away: I checked, and there is **no vector
index** on `kb_chunks.embedding` — not HNSW, not IVFFlat, just the primary
key. Every retrieval query is a full sequential scan. At 60 rows that's
genuinely irrelevant (sub-millisecond either way), but it means the
Postgres-vs-dedicated-vector-DB argument above is currently untested at
the scale where it would actually matter — there's no evidence yet that
pgvector indexing keeps pace as the knowledge base grows past a trivial
size. Worth adding an HNSW index via a new migration before the KB
expands materially past its current 20 articles — noted here rather than
quietly left for someone to discover later.
