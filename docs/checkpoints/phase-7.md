# Phase 7 checkpoint — customer-facing portal

This phase exists because of a gap that surfaced directly while showing
Phase 6's redesigned console: the product only ever had an agent side.
There was no way to demo the actual loop — a customer asking something real
and getting a real, reviewed answer back — without handing out live agent
credentials, which is both a security problem and, in an interview, means
describing half the system instead of showing it. This is exactly the
problem `BUILD_SPEC.md`'s own Phase 7 section names.

## Minimal auth: no password, a scoping column instead of a permission check

**What did you actually build?** A public `/portal` surface with no login
in the conventional sense — `GET /portal/customers` lists 8-10 seeded demo
customers, picking one just stores their id in `localStorage`, and every
subsequent portal request trusts that id at face value. The only thing
standing between this and "anyone can see anyone's tickets" is a single
column: `customers.display_name`, `NULL` for every real agent-side
customer, set only for the seeded demo ones. Every portal endpoint filters
on `display_name IS NOT NULL` before it will look at a `customer_id` at
all — a real customer's id gets the identical 404 a made-up UUID does.

**Why this approach, and what else did you consider?** Considered a
lightweight signed token (a JWT with `type: "customer"`, no password,
structurally rejected by the agent auth's `type != "access"` check) —
rejected as unnecessary ceremony. The spec is explicit that this is a demo
surface and shouldn't get real engineering effort spent on it, and a token
whose only job is "prove you picked a name from a public list" doesn't
protect anything a plain id doesn't already fail to protect, since the
list itself is public. The actual security boundary was never going to be
"can this id be forged" — it's "can a forged or wrong id ever reach real
customer data," which is what the `display_name IS NOT NULL` scoping
guarantees regardless of how trustworthy the id itself is.

**What's the failure mode if this were wrong or missing?** Tested
directly, not assumed: a real agent-side customer's id, taken straight
from the production database, was submitted to all three portal endpoints
(`GET .../tickets`, `GET /portal/tickets/{id}`, `POST /portal/tickets`)
and got a `404 "Demo customer not found"` from every one. If the
`display_name IS NOT NULL` filter were missing or wrong, this would
instead leak a real customer's ticket history to an unauthenticated
public endpoint — the worst-case failure here is a real data exposure, not
a cosmetic bug, which is why it was verified against a real customer id
rather than just a nonexistent one.

**Sharp follow-up question, honestly answered:** *"What stops someone from
enumerating ticket ids and reading other demo customers' tickets, even if
they can't reach real ones?"* — Nothing does, and that's a deliberate,
accepted gap, not an oversight. Every demo customer's data is synthetic —
seeded CFPB complaint narratives with no real person behind them — so
cross-demo-customer visibility costs nothing. The boundary that actually
matters (real vs. demo) is the one that was built and tested; the boundary
that wouldn't matter (demo vs. demo) wasn't, on purpose.

---

## Live status: polling, not WebSockets

**What did you actually build?** `/portal/tickets/[id]` and the inline
status panel on `/portal/new` both poll `GET /portal/tickets/{id}` every
1.5-3 seconds and render the same shared `PipelineTrace` component the
agent console uses — reused completely unmodified, only the stage
definitions passed into it differ.

**Why this approach, and what else did you consider?** WebSockets would
give sub-second updates, but ticket resolution here takes seconds to tens
of seconds (a real LangGraph pipeline run — measured at 14-45 seconds
locally depending on cold-start, per Phase 6's checkpoint) and then an
indeterminate wait for a human agent to actually click approve. Holding a
persistent connection open for a process whose fastest leg is measured in
seconds, not milliseconds, buys nothing a 1.5-second poll doesn't already
deliver, while adding real infrastructure (a WebSocket-capable deployment
target, connection lifecycle handling, reconnect logic) for no perceptible
benefit to the person waiting.

**What's the failure mode if this were wrong or missing?** Not applicable
in the sense of a bug — the actual risk with polling is unnecessary load
if intervals were too aggressive or connections too numerous. At this
scale (a demo surface, single-digit concurrent viewers) that risk doesn't
materialize; the honest tradeoff being made is optimizing for
implementation simplicity over update latency, in a case where the latency
difference is invisible to the person waiting.

**Sharp follow-up question, honestly answered:** *"What happens if 10,000
customers are polling their tickets at once?"* — This would fall over
before a WebSocket approach would, since every poll is a full HTTP
request/response cycle. That's a real, known limitation, not hidden —
it's an acceptable one for a demo surface, and would be the first thing to
revisit if this were ever a real product at real scale, not something
this phase pretends isn't a tradeoff.

---

## Fast-path approval, not full auto-send, as the default

**What did you actually build?** `decide()` now also returns
`fast_path_eligible: bool` — true when a draft is low-urgency
(`urgency_score < 0.4`), high-confidence (`>= 0.7`), tightly matched
against the knowledge base (`avg_retrieval_similarity >= 0.7`), and not in
the `dispute` category. That flag rides along on the `TicketDraft` row and
surfaces in the agent queue — but it still requires a human agent to click
"Approve draft," the exact same button and endpoint every other ticket
uses. Nothing about fast-path skips human review; it only marks which
drafts are safe to review fast.

**Why this approach, and what else did you consider?** The category
taxonomy turned out not to cleanly separate "generic FAQ" from "my
specific transaction" — every one of the five categories (`payment_failure`,
`refund_delay`, `account_lock`, `dispute`, `general_query`) has both kinds
of question in its training templates, confirmed by reading the actual
templates rather than assuming category alone would work. So eligibility
leans on the signals that really do separate them: a low-urgency question
the classifier is confident about and the knowledge base answers tightly
is much more likely to be a policy/limits/timelines question than an
account-specific one, regardless of which of the five labels it landed on.
`dispute` is excluded outright, not just by the numbers, since it's the
one category already carrying fraud-adjacent specialist routing in
`decide()` — that exclusion is a principle, not a coincidence of
thresholds.

**What's the failure mode if this were wrong or missing?** A ticket that's
actually account-specific but happens to score low-urgency/high-confidence
(e.g. a well-written, unambiguous question the model is confident about
purely because it's clearly worded, not because it's generic) could get
fast-tracked for a quicker glance than it deserves. This is why fast-path
never removes the human step — the worst case is an agent spending less
time on a ticket than an infinite-caution system would have made them, not
an unreviewed message reaching a customer.

**Sharp follow-up question, honestly answered:** *"Couldn't a chatbot just
answer everything, skipping the queue entirely?"* — For the narrow slice
fast-path targets (generic, tightly-KB-matched, low-stakes questions),
maybe — and `AUTO_RESOLVE_THRESHOLD` below is exactly that experiment,
deliberately fenced off. For everything else, no: this is a fintech
support surface, and "my specific transaction" questions need a lookup a
generic chatbot can't do without account access, and fraud-adjacent
disputes need judgment a confidence score doesn't capture. The honest
line isn't "AI vs. human," it's "which tickets are pure lookups a
tightly-matched KB article already answers, and which need someone to
actually look at the account" — fast-path targets exactly the first
group, and still keeps a human in the loop even there.

---

## AUTO_RESOLVE_THRESHOLD: built, tested, off by default

**What did you actually build?** A `Settings.auto_resolve_threshold: float
| None = None` config flag. When set, a ticket that's both fast-path
eligible and whose confidence clears the threshold resolves with zero
human touch — the only path in `decide()` that ever sets
`needs_review=False`, everywhere else that stays hard-coded `True`. Since
`TicketResolution.agent_id` is a `NOT NULL` foreign key, auto-resolution
needed a real `User` row to attribute to — a seeded sentinel
`system@resolveiq.internal` account, never logged into (its password is a
random 32-byte token, discarded immediately). The audit log marks these
distinctly: `event_type="auto_resolved"`, `detail.resolved_by: "ai_auto"`
— never folded into the same event type a human "approved" action uses,
so the audit trail always shows whether a person was involved.

**Why this approach, and what else did you consider?** Considered making
`agent_id` nullable instead of seeding a sentinel user — rejected because
it would have meant a real schema change (loosening a constraint) to work
around a one-off case, versus a sentinel row that satisfies the existing
constraint with zero schema risk. The threshold itself defaults to `None`
(disabled) rather than a low default value, specifically so a fresh
deployment never auto-resolves anything unless someone deliberately opts
in — it exists to demonstrate the tradeoff was considered, not to be the
demo's default behavior.

**What's the failure mode if this were wrong or missing?** Fully unit
tested rather than left to informal reasoning: `test_decision.py` covers
the threshold being unset (`auto_resolved` stays `False` even when
everything else about a ticket would qualify), confidence just below the
threshold (doesn't fire), and fast-path-ineligible tickets at high
confidence (doesn't fire even above threshold) — 19 tests total in that
file now, 10 of them new for this phase, all passing. If the gating logic
were wrong, the failure mode is exactly what the "core rule" test
(`test_every_outcome_always_needs_review`) exists to catch: a ticket
resolving without any human ever seeing it, silently.

**Sharp follow-up question, honestly answered:** *"If it's off by
default and untested in a live run, how do you know it actually works,
not just that the unit tests pass?"* — Fair, and worth being precise
about the boundary of what was actually verified here (see the status
section below): the decision logic itself is unit-tested end-to-end
including the auto-resolve branch, and the `TicketResolution`/`AuditLog`
write path was verified by direct code read against the exact same
pattern the human-resolve endpoint already uses successfully in
production. What was *not* verified is watching a real ticket auto-resolve
through the live Celery worker, because the local network blocked the
Redis broker for the second half of this session (documented below) —
that's an honest gap, not a claim of full live verification.

---

## A real finding while testing: `process_ticket.delay()` can wedge the whole server, not just fail

**What did you actually build?** Nothing new — this is a bug found while
trying to verify the portal end-to-end, worth recording because it would
matter to anyone deploying this, not just this phase.

**What happened?** Partway through verification the local network blocked
port 6379 again (the same intermittent block documented in Phase 5 and
earlier this session — it had briefly opened, which is what made starting
this phase's work possible in the first place, then closed again). A
`POST /portal/tickets` call was made to test the submission endpoint; it
hung past a 10-second timeout. Tested whether this was specific to the new
portal code by sending the exact same kind of request to the *existing*,
already-shipped agent-side `POST /tickets` endpoint — it hung identically,
confirming this isn't something Phase 7 introduced. The real finding:
a *subsequent, unrelated* `GET` request to a different endpoint also hung
and timed out. `process_ticket.delay()` is a synchronous, blocking Celery
call made from inside an `async def` FastAPI route with no `await` or
thread offload — when the broker is unreachable, it doesn't just fail
that one request, it blocks uvicorn's single-threaded event loop from
serving anything else until Celery's own internal retry/timeout gives up.

**What's the failure mode if this were wrong or missing?** Exactly what
was observed: a ticket-submission endpoint that, under a broker outage,
doesn't fail fast with a clean error — it silently wedges the entire API
for every other user, including ones not submitting tickets at all. This
is worse than a normal single-request failure, and it's a pre-existing
characteristic of both submission endpoints, not something new.

**Fix and re-verification:** No code change made — restarting the wedged
uvicorn process was the immediate fix, and confirmed the read endpoints
(`GET /portal/tickets/{id}`, `GET /portal/customers/{id}/tickets`) worked
correctly against real data once the server was fresh again. Actually
fixing the underlying issue (offloading `.delay()` to a thread, or making
it fail fast instead of blocking) would be a real improvement but touches
the pre-existing agent-side endpoint too — out of scope for this phase,
which reused that exact code path deliberately (see the spec's own
instruction: "no separate pipeline path"). Noted here as a real,
verified gap rather than silently worked around.

**Sharp follow-up question, honestly answered:** *"Why not just fix it
while you were in there?"* — Because the fix belongs to both endpoints
equally, and doing it as a drive-by inside a portal-feature phase would
bury an infrastructure fix inside an unrelated commit, making it harder to
review and easier to get wrong under time pressure. It's flagged here
explicitly so it's a known, prioritizable item, not quietly patched over.

---

## Status at time of writing

**Verified against real data:** the migration (two nullable `customers`
columns, one defaulted `ticket_drafts` boolean) applied cleanly to the
real production Neon database. The seed script created a sentinel system
user, 10 demo customers, and 30 resolved history tickets pulled from real
CFPB-derived complaint narratives (Phase 3's cached dataset) — confirmed
correct, including non-ASCII names (`Noah Bergström`), by reading the raw
UTF-8 codepoints directly rather than trusting a Windows console's display
of them, which mangled the character purely cosmetically. All 54 backend
tests pass, 10 of them new for this phase's decision logic. The security
boundary (`display_name IS NOT NULL`) was tested against a real
production customer id at all three portal endpoints, not just a
nonexistent one, and held every time. The frontend was verified with real
screenshots against a real running server: the customer picker, the
submission form, and the status page in both a pending and an already-
resolved state — the resolved-state screenshot shows real seeded data,
the customer-safe three-stage trace, and the reply panel rendering
correctly. The portal-submitted ticket was confirmed visible through the
*agent-side* API with the correct channel (`"portal"`) and correct
customer history, proving there's genuinely one pipeline, not two.

**The full live run, completed once the network cooperated.** The
network's port-6379 block was intermittent, not permanent — it reopened
later in the same session, and the walk this checkpoint originally
couldn't complete was then run for real: a genuine question ("What is
your standard policy on how long refunds usually take to process once
approved?") submitted through the actual `/portal/new` UI as seeded demo
customer Priya Natarajan, picked up by a freshly reconnected Celery
worker, classified `refund_delay` with real urgency (0.14) and confidence
(0.47) scores, drafted by a real Groq call citing five real knowledge-base
chunks. The trace advanced through real state changes captured mid-run,
not just a before/after: `Received` done almost immediately, `Under
review` active for roughly a minute while the pipeline actually ran, then
flipping to done once it finished — confirming the two portal stages
really do correspond to two distinct real-world events (pipeline
completion vs. human resolution), unlike the agent-side trace's
single-commit jump documented in Phase 6.

This run also exercised the fast-path logic against real numbers instead
of only synthetic unit-test inputs: confidence (0.47) and retrieval
similarity (0.58) both legitimately fell short of the 0.7 fast-path
thresholds despite the question being genuinely FAQ-shaped, so it
correctly stayed a standard review (`"Standard review — draft ready for
agent approval."`) rather than fast-pathing — real evidence the
thresholds require the model to actually be confident and the retrieval
to actually be tight, not just that a question sounds generic. The
ticket was then approved through the real agent `/resolve` endpoint
(the same one-click action any agent would use), and the portal's status
page — reloaded fresh, not the same tab — showed exactly and only what a
customer should see: all three stages green and the reply text, with no
confidence score, no specialist flag, no cited sources, and no internal
routing detail anywhere on the page.

**Still not exercised live:** `AUTO_RESOLVE_THRESHOLD` firing in practice
(it stayed at its default `None` throughout this run, correctly, since
turning it on wasn't part of this phase's default-state verification) and
the fast-path-eligible=true case specifically (this run's real numbers
happened to fall just short of the threshold). Both are covered by the
unit tests in `test_decision.py`, including the exact boundary cases, but
neither has been watched happen against a real ticket end to end. That's
a narrower, more honest gap than the one this checkpoint started with.
