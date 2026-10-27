# Phase 9 checkpoint — stretch items, and a real production outage found along the way

`BUILD_SPEC.md` scoped Phase 9 as optional stretch work, to attempt only once
Phases 1-8 were solid. In practice this phase started with a "is everything
actually still working?" check before touching anything new — and that
check surfaced a real, live production outage that had nothing to do with
any of the four stretch items below. Fixing it turned out to matter more
than any one of them, so it's documented first.

## The outage: Hugging Face's hosted embeddings API had run out of credits

**What was actually broken?** `app/kb/embeddings.py` calls HF's hosted
Inference API for every embedding — both the one-time KB article embed
script *and*, critically, `embed_text()` inside `app/retrieval/retrieve.py`,
which runs on **every single real ticket** to embed the incoming query
before retrieval. That call started returning `402 Payment Required`:
`"You have no remaining credits. Purchase pre-paid credits to continue
using Inference Providers."` HF's free Inference Providers allowance is a
*monthly* quota, not a permanent free tier, and it had run out. Every
ticket submitted in this state would fail retrieval and, with it, the
entire pipeline — confirmed directly by reproducing the 402 against the
real endpoint with the real configured key, not assumed from a changelog.

**Why didn't this get caught earlier?** The Phase 7 checkpoint's live
walkthrough genuinely worked, citing five real KB chunks — that was true
at the time and the credits ran out sometime after. This is the second
time an embedding provider's "free tier" turned out not to be free in
practice (the first was Gemini's "prepayment credits depleted" paywall,
which is *why* this moved to HF in the first place) — worth remembering
as a pattern, not a one-off: hosted free tiers for anything embedding- or
inference-shaped are a liability for a long-running demo, not a solved
problem.

**The fix, attempt 1 (deployed, then found insufficient):** `embed_texts()`
tries the hosted API first and, on any failure, falls back to computing
the exact same model locally via the `sentence-transformers` package.
Verified correct against the real database — re-ran `uv run python -m
app.kb.embed`, which embedded all 25 KB documents (77 chunks) entirely via
the fallback, and real retrieval queries through `app.retrieval.retrieve`
confirmed the resulting vectors still rank correctly (*"my refund is
taking too long"* top-matched the refund timeline articles at 0.61/0.60
similarity; *"I want to close my account"* top-matched every chunk of the
new account-closure article). But this was deployed before checking
whether it could actually *run* in production, and it couldn't:
`requirements-deploy.txt` deliberately excludes `sentence-transformers`
(same 512MB-worker reason it excludes `torch`/`unsloth` — see
`docs/checkpoints/phase-5.md`), so on Render the fallback's own import
wasn't available. Caught by checking the real deploy config right after
pushing, not assumed to have worked everywhere it was written to work.

**The fix, attempt 2 (what's actually deployed now): the same model's
published ONNX export, run via `onnxruntime` + a raw `tokenizers`
tokenizer — no torch, no `sentence-transformers`.** `onnxruntime` +
`tokenizers` + `huggingface-hub` together are ~30MB of wheels, and the
model file itself is a ~90MB `.onnx` baked into the Docker image at build
time (`Dockerfile.deploy`), versus torch's own ~385MB runtime footprint —
light enough to actually fit the worker's budget instead of just fitting
it in theory.

**Verified equivalent, not assumed equivalent because "it's the same
model":** before trusting this, ran both implementations side by side on
three real support-ticket-style queries and compared the resulting
vectors directly — cosine similarity **1.000000** between the ONNX output
and the `sentence-transformers` reference for every one of them, not an
approximate match. Re-ran the KB embed and the retrieval sanity queries
above through the new ONNX path afterward and got the same rankings
again. Also exercised the "baked into the image" code path specifically
(not just the Hub-download path available in local dev) by placing the
two files where `Dockerfile.deploy` puts them and confirming
`embed_texts()` picks them up and returns correctly-shaped vectors — the
part of this fix that actually reaches the deployed worker, checked
directly rather than inferred from the Dockerfile reading correctly.

**Honest residual gap:** the Docker build itself (the actual `docker
build` of `Dockerfile.deploy`, with the real `RUN` step downloading and
baking the two files) has not been run on this machine — Docker is
unusable here (a standing constraint on this project, unrelated to this
fix) — so the *build step's* correctness is reasoned through and each
piece tested in isolation (the download-and-copy Python snippet, the
baked-file code path, the ONNX-vs-reference equivalence) rather than
verified end-to-end as one real build. Render's own build log on the next
deploy is the first real end-to-end confirmation.

## 1. Ticket claim/assignment

**What was actually built?** `tickets.assigned_agent_id` existed on the
schema since Phase 1 but nothing ever set or checked it — two agents could
open and resolve the same ticket blind, each unaware of the other.
`POST /tickets/{id}/claim` and `/unclaim` now set/clear it under the same
row-level `with_for_update` lock `resolve_ticket` already used for the
double-resolve guard, and `resolve_ticket` itself now refuses (409) to
resolve a ticket claimed by a different agent. An unclaimed ticket is
silently self-claimed by whoever resolves it, so the common single-step
"open it and approve" flow needs no separate claim call — claiming
up-front only matters when an agent wants to signal "I'm on this" before
acting.

**Why this design, not a stricter one?** Considered making claiming
mandatory before any resolve action. Rejected: it would add a click to
every single-agent demo walkthrough for a race condition that only
matters with multiple agents working concurrently, and the self-claim-on-
resolve behavior already closes the actual race (the row lock means only
one of two simultaneous resolve attempts can win, and the loser gets a
real 409, not a silent double-resolution).

**Tested:** 9 new tests (`test_ticket_claim.py`) covering claim, re-claim
by the same agent (idempotent), claim-conflict with a second real agent
user, unclaim, unclaim-conflict, resolve-auto-claims, resolve-blocked-by-
another-agent's-claim, and the 404 case.

## 2. An actual branch in the LangGraph pipeline for specialist-flagged tickets

**What was actually built?** The graph was linear end-to-end; `decide()`'s
`specialist_flagged` was state attached to the ticket, never anything that
changed what the pipeline itself did. There's now one real conditional
edge: `add_conditional_edges("decide", route_after_decide, {...})` sends a
specialist-flagged ticket (low draft confidence, or a high-urgency
dispute) through a new `specialist_review_node` before `END`; a routine
ticket skips straight there. That node re-retrieves with a wider `top_k=8`
(vs. the standard 5) and forces the strong-tier model via a new
`force_strong_tier` parameter on `draft()`, regardless of what the
urgency-based tier selection would have picked — a genuinely more
expensive, better-grounded second attempt, done automatically before an
agent ever opens the ticket, not left as a flag for the agent to notice or
ignore.

**Why a second draft rather than just richer flagging?** The flag alone
told an agent "be careful," but handed them the exact same draft a routine
ticket would have gotten — the system already knew this was a hard case
and ended up giving it less effort, not more. Re-running retrieval and
drafting here trades latency/cost (one extra retrieval + one extra strong-
tier generation call) for a draft that's actually earned the "needs
specialist review" label change it's about to get in front of a human,
which is the one place in this pipeline where paying that cost is
clearly worth it.

**Why `route_after_decide` is a module-level function, not a closure:** so
it's unit-testable against a bare `{"decision": Decision(...)}` dict with
no DB session and no compiled graph — four tests
(`test_graph_routing.py`) pin every branch of the routing decision
directly, including the invariant that an auto-resolved ticket is never
also specialist-flagged. A separate two-test suite
(`test_pipeline_specialist_branch.py`) goes one level up and exercises the
*real* compiled graph with every model/retrieval call stubbed, confirming
`add_conditional_edges` is wired correctly and the specialist pass is
genuinely reached (and only then) — proving the LangGraph wiring itself
works, not just the router function in isolation. `test_drafting.py`
gained two more tests confirming `force_strong_tier=True` actually
bypasses the cheap-tier urgency check.

**What's still not exercised against a real model call end-to-end:** the
specialist-review node has been proven correct against stubbed
draft/retrieve calls, and `force_strong_tier` has been proven to pick the
strong tier against a stubbed Groq call — but a real low-confidence ticket
has not yet been walked through the full live pipeline with a real Groq
call for the specialist pass specifically (the Phase 7 checkpoint's live
walkthrough predates this branch existing at all). That's a narrower gap
than "untested," but it's not nothing.

## 3. Expanded the knowledge base past 20 articles

**What was actually underrepresented, and how was that decided?** Not
guessed — read directly off `app/ml/cfpb_data.py`'s own
`ISSUE_TO_CATEGORY` mapping, which is the real CFPB issue taxonomy each
category is built from. Every category had exactly 4 articles regardless
of how many distinct real-world issue subtypes map into it, so the
categories with the most issue-subtype diversity relative to their
article count were the real gaps, not an arbitrary round number:

- **dispute** (8 issue subtypes, 4 articles, all about the dispute
  *process*): added **Identity Theft and Fraud — What To Do**, since
  `"Fraud or scam"` and `"Identity theft / Fraud / Embezzlement"` need
  security actions (suspend access, credit freeze) that a billing-dispute
  article never covers.
- **general_query** (10 issue subtypes — the most of any category — 4
  articles, only one of which touched fees at all): added **Late Fees and
  How to Dispute Them**, since `"Late fee"` is its own distinct, common
  issue subtype the generic statement/fees article didn't specifically
  address.
- **payment_failure**: added **Payment Taken for the Wrong Amount or on
  the Wrong Date**, distinct from the existing duplicate-charge article —
  `"Money was taken ... on the wrong day or for the wrong amount"` is a
  timing/amount error, not an extra charge.
- **account_lock**: added **Closing Your Account — What to Expect** — 3 of
  7 issue subtypes (`"Closing an account"` / `"Closing your account"` /
  `"Closing/Cancelling account"`) are customer-*initiated* closure, and
  all 4 existing articles were about being locked *out*, the opposite
  scenario.
- **refund_delay**: added **Lost or Stolen Refund — What To Do** —
  `"Lost or stolen refund"` / `"Lost or stolen money order"` means the
  refund never arrives at all, a different problem from the existing
  articles' "it's taking longer than the standard window."

**Verified, not assumed:** re-embedded all 25 documents (see the outage
section above) and ran real retrieval queries confirming each new article
actually out-ranks the existing ones for the query it was written to
answer, not just that it exists in the database.

## 4. CI/CD: GitHub Actions runs the backend suite on every push

**What was actually built?** `.github/workflows/ci.yml` runs on push/PR to
main: `pgvector/pgvector:pg16` and `redis:7` as GitHub-hosted service
containers (not Docker-on-this-machine — that's a settled "never again"
from earlier in this project, and service containers are a different,
GitHub-managed mechanism), a step that explicitly `CREATE EXTENSION IF NOT
EXISTS vector` since a fresh service container starts without it even
though `pgvector/pgvector` ships the extension files, then `uv sync` and
`uv run pytest -v`. No env vars are faked: every `app/core/config.py`
setting already has a safe default (database/redis URLs already point at
localhost, matching the service containers; `groq_api_key`/`hf_api_key`
default to `None` and nothing in the suite makes a real model call).

**A second, unplanned fix found along the way:** the local Postgres/Redis
this whole test suite depends on are WSL2 services, and WSL2 tears down an
idle distro's VM instance a few seconds after the last attached process
exits by default — meaning a fresh terminal running `pytest` minutes after
the services were "started" would hit a cold `ConnectionRefusedError`
that looked like a flaky environment but was actually `wsl -l -v` quietly
showing `Stopped` the whole time. `systemctl is-enabled` showed the
services were enabled, but WSL2 doesn't run systemd as PID 1 by default,
so "enabled" never meant "actually started." Fixed two ways:
`/etc/wsl.conf`'s `[boot] systemd=true` so the services' own `enabled`
state is honored on every boot, and a persistent `wsl -d Ubuntu -- bash -lc
"sleep infinity"` process kept attached so the distro itself doesn't idle-
shut-down between work sessions. Confirmed by waiting past the old timeout
window from a cold, separate command and reconnecting successfully —
this had been silently causing the "63 errors, all ConnectionRefusedError"
failure mode intermittently throughout this project's whole local-dev
history, not a one-time fluke.

## Honest gaps after this phase

- The specialist-review branch's real-Groq-call path (not just its
  stubbed-call-correct wiring) hasn't been walked end-to-end yet.
- CI has not yet had a real push/PR run against it on GitHub's
  infrastructure — only reasoned through and checked against local
  equivalents (the exact service-container versions, the exact env
  defaults). The first real push is the first real verification.
- The HF quota could run out again on any given day — the local fallback
  means the pipeline keeps working either way, but it's worth knowing
  going into a demo that a cold start on the fallback path pays a few
  extra seconds loading the local model the first time a process hits it.
