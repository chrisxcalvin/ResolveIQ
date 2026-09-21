# Phase 5 checkpoint — deployment

This phase took far longer than the previous four combined, almost
entirely because of a chain of "free tier" claims that turned out not to
hold up under an actual test. That chain is most of what's worth learning
from here, more than the final architecture is.

## Platform choice: why Render, not Railway

**What did you actually build?** Deployed the API and worker to Render,
not Railway — despite Railway being the spec's first recommendation and
having the nicer CLI-driven deploy flow.

**Why this approach, and what else did you consider?** Tried Railway
first. Its free trial credit had already been used on the account being
deployed from, and Railway now requires a payment method on file for
anything beyond that — usage-based billing, not expensive, but a real
recurring cost I wasn't going to opt into on someone's behalf without
asking. Switched to Render specifically because its free tier doesn't
require a card at all for a Web Service, at the cost of more manual setup
(no CLI-driven deploy, had to hand-configure through their dashboard).

**What's the failure mode if this were wrong or missing?** Not really
applicable here — this was a cost decision, not a correctness one. The
failure mode of getting it wrong would just be an unexpected charge on
someone's card.

**Sharp follow-up question, honestly answered:** *"Why not just pay the
few dollars and save the time?"* — Because it wasn't going to be a few
dollars. See the memory section below: the tier that would have
comfortably fit this workload on Render is $25/month (Standard, 2GB), not
the $7/month Starter tier I initially assumed — Starter is still capped
at 512MB, same as free. Once "small paid tier" turned out to mean $25/mo
not $7/mo, spending more engineering time to stay free became the
obviously better trade.

---

## The lean deployment image, and a dependency gap it exposed

**What did you actually build?** A separate `Dockerfile.deploy` /
`requirements-deploy.txt`, not the dev `Dockerfile`'s `uv sync` against
the full `pyproject.toml`. Excludes Unsloth and the CUDA torch build
entirely (confirmed via grep that `unsloth` is never imported at module
level anywhere — only lazily inside `cheap_tier.py`'s `_load_model()`,
which is never reached when `CHEAP_TIER_URGENCY_THRESHOLD=0`), and
excludes `ragas`/`langchain-community` (confirmed eval-only, unreferenced
in the serving path).

**Why this approach, and what else did you consider?** Could have kept
one dependency file and just accepted the 10-20GB image the dev
Dockerfile already warned about. Rejected — that's not "less effort," per
the build spec's own framing, it's committing a multi-gigabyte build to a
free-tier build-time/size budget for a model that will never run.

Building the curated list by hand from `pyproject.toml`'s explicit
dependencies missed something: `app/ml/breach_risk.py` imports `pandas`
directly for live breach-risk scoring, but `pandas` was never an explicit
top-level dependency — it arrived locally only as a transitive dependency
of `ragas`/`langchain-community`, both deliberately excluded. First deploy
attempt crash-looped on `ModuleNotFoundError: No module named 'pandas'`.
Fixed the immediate bug, then fixed the actual process: wrote a small AST
scanner that walks every serving-path module's real imports and diffs
them against `requirements-deploy.txt`, rather than continuing to trust
the top-level dependency list was complete. It wasn't, and `pandas` was
the only gap it found.

**What's the failure mode if this were wrong or missing?** Exactly what
happened — a clean-looking build that crash-loops the instant it hits the
code path needing the missing package. Silent until that exact line
executes; nothing about the missing dependency shows up before then.

**Sharp follow-up question, honestly answered:** *"How do you know
there isn't a second missing package you haven't hit yet?"* — I don't,
with 100% certainty, from static analysis alone. What I do have is a real
test: installed the exact `requirements-deploy.txt` into a fresh,
isolated virtualenv and successfully imported `app.main` and `app.tasks`
end-to-end in it, which is the actual thing that has to succeed on
Render. That's stronger evidence than the AST scan alone, though it's
still not literally the same OS/container Render builds in.

---

## Render's Background Worker paywall, and the two-service split

**What did you actually build?** Two separate free Render Web Services —
`resolveiq-api` and `resolveiq-worker` — instead of one Background Worker
service (which requires a paid plan) and instead of the first version of
this fix, which combined both processes into one Web Service container.

**Why this approach, and what else did you consider?** The combined-container
version was the first attempt: `start-render.sh` backgrounded the Celery
worker and exec'd uvicorn in the foreground, one container, one free
service. It got further than a naive attempt (past the build, into
actually running), then hit `Ran out of memory (used over 512MB)` — both
processes were independently importing the entire pipeline's dependency
tree.

Splitting into two services solves the "two processes sharing one
budget" problem, but Render's Web Service type requires binding to
`$PORT` and answering a health check, which a bare Celery worker doesn't
do. `start-worker.sh` runs a deliberately trivial always-200 HTTP handler
in a background thread alongside the real worker — just enough to satisfy
Render's requirement, not a real health signal (it can't report the
worker's actual state, e.g. whether it's connected to Redis).

**What's the failure mode if this were wrong or missing?** If both
processes stayed combined: an OOM crash loop that never stabilizes — the
container restarts, runs migrations, starts both processes, OOMs again,
forever, which is exactly what the logs showed before this fix. If the
worker's fake health endpoint were missing entirely: Render would never
consider the worker service healthy and would keep restarting it even if
the actual Celery process were running fine underneath.

**Sharp follow-up question, honestly answered:** *"Doesn't a fake health
check defeat the point of having one?"* — Partially, yes, and worth being
direct about it rather than presenting it as a clean solution. It proves
the container is alive and listening, not that Celery is actually
connected to Redis and processing tasks. A more honest health check would
have the worker process itself report its Redis connection state to the
tiny HTTP handler (e.g. a shared flag set on successful broker connection).
Didn't build that here — noted as a real gap, not hidden.

---

## The memory investigation: three attempts before it actually fit

This is the part of the phase worth understanding in the most detail,
because "we hit a memory limit and fixed it" undersells how many times
the first fix looked sufficient and wasn't.

**Attempt 1 — lazy-import torch/spaCy in the API process.** The API
process (`uvicorn`) was loading torch and spaCy into memory on startup
despite never calling `embed_text()` or `redact()` itself — it only
imports `app.tasks.process_ticket` to reference it for `.delay()`, and
that import chain transitively pulled in the whole pipeline. Deferred
both imports inside their `_load_model()`/`_load_nlp()` functions
(the same lazy pattern already used for Unsloth). Verified: API process
memory after import dropped from a level that was clearly contributing to
the crash to 217MB, measured directly in an isolated venv with `psutil`,
not estimated.

This fix was real and necessary. It was not sufficient — see attempt 2.

**Attempt 2 — actually measuring the worker's real memory, not just its
imports.** Import-time memory isn't the whole story for the worker,
because the worker's whole job is to *call* `embed_text()` and `redact()`
for real. Ran both for real in the isolated venv and measured: 208MB
baseline → 593MB after the first real `embed_text()` call (torch, loading)
→ 662MB after the first real `redact()` call (spaCy's model). The worker
needed 662MB **alone**, over the 512MB limit before the API process would
even have shared the container. Splitting into two services (attempt
above) would not have fixed this on its own — 662MB doesn't fit in 512MB
regardless of what else is or isn't sharing it.

**Attempt 3 — the fix that actually worked.** Two changes together:
(1) `app/kb/embeddings.py` now calls a hosted embedding API instead of
loading a local sentence-transformers/torch model — this removes torch
from the worker's memory footprint entirely, not just delays loading it;
(2) `app/redaction/pii.py` now loads spaCy with only the `ner`/`tok2vec`
pipeline components the code actually uses (`doc.ents`), disabling
`tagger`/`parser`/`attribute_ruler`/`lemmatizer`, which the code never
reads. Re-measured in the same isolated venv: 209MB baseline → 213MB
after `embed_text()` (an HTTP call now, not a model load) → 287MB after
`redact()`. 287MB, comfortably under 512MB with real headroom, not a
near-miss.

**Why hosted embeddings over other options?** Considered upgrading to
Render Standard ($25/month, 2GB) instead of any of this. Rejected as the
first choice specifically because the actual fix was findable and free —
see the honest cost comparison in the platform-choice section above.
Considered ONNX runtime as a lighter local alternative to full torch;
tried it, hit real dependency conflicts (`sentence-transformers`
requiring a newer `huggingface-hub`/`transformers` than what installed
cleanly alongside `optimum[onnxruntime]`) within minutes, abandoned it
rather than burn more time on an uncertain path when a hosted-API
alternative was available and simpler to verify.

**What's the failure mode if this were wrong or missing?** Precisely
what happened twice already in this phase: a deploy that builds
successfully, starts, and then dies specifically once real traffic
exercises the code path that loads the missing memory — which is why
static inspection (reading the code, checking the Dockerfile) wasn't
enough either time. Both real findings here came from *running* the code
in an isolated environment and measuring, not from reasoning about it.

**Sharp follow-up question, honestly answered:** *"Doesn't switching to
a hosted embedding API introduce a new external dependency and a new
point of failure the local-model version didn't have?"* — Yes, directly.
The original embeddings module's own docstring said "no external
API/key needed" as a deliberate design property, and this phase removed
that property. The trade being made explicitly: a small, real dependency
on a third-party API's uptime and rate limits, in exchange for the
deployment fitting in a free container at all. If Hugging Face's
Inference API has an outage, ticket drafting degrades (retrieval would
fail, triggering the "no relevant knowledge base information" refusal
path — not a crash, but a real quality regression) until it recovers.
That's a real, accepted trade-off, not something hidden by the fix.

---

## Verify, don't trust: the Gemini paywall, and getting Hugging Face right on the second try

**What did you actually build?** Ended up on Hugging Face's Inference API
for embeddings. Got there by first building and shipping a whole
implementation against Google's Gemini embedding API, based on multiple
web sources describing it as free (1,500 requests/day, no card required),
then hitting a real `402 Payment Required — Your prepayment credits are
depleted` on the first actual call.

**Why this approach, and what else did you consider?** The Gemini
implementation itself was reasonable engineering — correct endpoint,
correct auth header, dimensionality truncated to match the existing
384-dim schema exactly. The problem wasn't the code, it was trusting
secondary sources (blog posts, pricing-comparison sites) about a
platform's current billing policy without confirming against the
platform directly. Same mistake pattern as Railway's trial and the
earlier Hugging Face GPU pricing question this session — three separate
times, a "free tier" claim from search results didn't survive an actual
API call.

Switched to Hugging Face specifically because, this time, verification
came *first*: made one real `curl` call against
`router.huggingface.co/hf-inference/.../feature-extraction` with a plain
Read-scope token before writing any implementation code, confirmed a
clean `200` with the exact `list[384]` shape needed, confirmed the batch
shape (`list[N]` of `list[384]`) separately, and only then wrote
`embeddings.py` against it. Also confirms the model is literally the same
`sentence-transformers/all-MiniLM-L6-v2` the app always used locally —
no dimension truncation needed, no risk of degraded embedding quality
from a different model.

**What's the failure mode if this were wrong or missing?** Already
happened once this phase in a slightly different form — an implementation
built against unverified claims about a service's terms, discovered wrong
only once real traffic (a real API call) hit it. The cost here was
wasted implementation time, not a production incident, but the shape of
the failure — "worked in every way except the one that actually
mattered" — is the same.

**Sharp follow-up question, honestly answered:** *"What stops the same
thing happening with Hugging Face's free tier six months from now?"*
Nothing structural — this project has now hit exactly that pattern twice
in one afternoon (Railway, Gemini) with services that were genuinely free
before and tightened their policy since. Hugging Face could do the same.
The honest mitigation isn't "pick a provider that definitely won't change
its pricing" — that's not knowable in advance — it's that `embed_text()`
already fails loudly (an `HTTPStatusError`, not a silent wrong answer) if
it ever does, and the refusal path in `app/drafting/draft.py` means a
retrieval failure degrades to "no relevant knowledge base information
found," not a crash or a hallucinated answer.

---

## A red herring worth documenting: the local network block

While re-verifying end-to-end after the embeddings fix, the local Celery
worker couldn't connect to Upstash — timing out on port 6379 specifically,
while HTTPS (443) to the same host and Postgres (5432) to Neon both
worked fine from the same machine. Isolated it with a raw socket test
across three ports rather than assuming it was another billing/config
issue: confirmed it's the current network (a college network, per the
DNS server visible in `nslookup`) blocking that specific port outbound,
not Upstash, not the code, and not something that affects Render's
deployment (different network entirely). Worth recording only because it
looked, for a few minutes, exactly like the previous two real paywall
findings — the discipline that told them apart was the same in both
cases: test directly, don't infer from the symptom's shape alone.

---

## Status at time of writing

Code-complete and locally verified (KB re-embedded against Neon using the
new Hugging Face-based pipeline, confirmed correct shape and dimension,
full test suite passing). The actual Render deploy of both services
(`resolveiq-api` with the fix, and the new `resolveiq-worker`) was in
progress when this checkpoint was written — a live end-to-end ticket
verification against the deployed URLs, in the same style as every
previous phase's live check, is the next thing to confirm before this
phase is genuinely done, not just theoretically fixed.
