# Phase 8 checkpoint — benchmarking, and the honest "what's your evidence" answer

`BUILD_SPEC.md` names the exact risk this phase exists to avoid: inventing
a plausible-sounding number like "reduces resolution time by 40%" is worse
than having no number at all, because a single follow-up question about
methodology exposes it. Everything in `BENCHMARKS.md` was actually run
against the real pipeline, real database, and real (if historical) ticket
text — nothing here is estimated.

## What was actually measured, and how

**Time-to-draft (n=30, automated):** `app/scripts/benchmark_time_to_draft.py`
submits real CFPB-derived complaint narratives through the exact same
`process_ticket.delay()` call a real ticket submission makes, one at a
time, each waited out before the next starts, and reads back
`TicketDraft.created_at - Ticket.created_at` — real server timestamps,
not a timer in the script. Run against a local Celery worker consuming
from the same production Redis broker (Upstash) and writing to the same
production database (Neon) the deployed app uses. Full numbers in
`BENCHMARKS.md`.

**Retrieval quality (RAGAS, re-run):** the existing 18-example hand-labeled
eval re-run after two real changes this round — the KB grew from 20 to 25
articles and every embedding got recomputed via a new local fallback path
(see `docs/checkpoints/phase-9.md`'s outage section) — specifically to
confirm neither change quietly degraded retrieval. Mean precision 0.800,
recall 0.639, and this is the *first* time these numbers have been
captured anywhere in this project's docs, so it's the baseline going
forward, not a comparison to a prior run.

**Manual-vs-assisted comparison and draft approval-rate: built, not yet
run.** `app/scripts/benchmark_manual_vs_assisted.py` reuses the real
tickets/drafts from the time-to-draft run and times a human two ways per
ticket — writing a reply from scratch, then reviewing/editing/rejecting
the real AI draft — logging both the timing and the approval
classification in one pass (the spec's items 2 and 3 are one script, not
two, since running the same 20 tickets through two separate human-timed
passes would double the real time cost for no additional honesty). This
is the one piece of Phase 8 that requires a human to actually sit and do
it — it was built and smoke-tested for mechanical correctness (no
crashes, correct data loading, correct APPROVE/REJECT/edit-distance
handling) but the *real* timed run is the developer's own work, not
something that can be substituted or faked. Once run, its results slot
into `BENCHMARKS.md`'s second section.

## Why this order, and why these methods specifically

**Why one-at-a-time submission for time-to-draft, not a burst of 30?**
The deployed worker is single-threaded by necessity (`--pool=solo`,
documented in `docs/checkpoints/phase-5.md`) — submitting all 30 at once
would measure queue-wait time stacking on top of real processing time,
and reporting that number as "time-to-draft" would conflate two different
things under one misleading label. One-at-a-time isolates per-ticket
service time, which is what "time-to-draft" is actually supposed to mean.

**Why combine the manual-vs-assisted comparison with the approval-rate
measurement into one script instead of two separate passes?** The spec
describes them as two measurements, but they're naturally the same human
action looked at two ways: timing how long the assisted review took *is*
timing the same action whose outcome (approved/edited/rejected) *is* the
approval-rate data. Splitting them into two separate passes over the same
20 tickets would have doubled the real human time cost to produce the
exact same two numbers from the exact same action.

**Why was RAGAS re-run instead of just trusting it still worked?**
Because two things changed since it last ran — the KB size and the
embedding backend — and "probably still fine" isn't evidence. Re-running
it and getting a real score is what confirms the KB expansion and the
embeddings outage fix (phase-9.md) didn't quietly make retrieval worse
while fixing/improving something else.

## The honest answer to "what's your evidence this actually works?"

Three real numbers, each with a stated scope: a 30-ticket real-pipeline
latency distribution (median 18.85s, p95 25.05s) that also surfaced two
specific, named findings — the cheap/strong tier split didn't engage the
cheap tier at all on this real-complaint-text sample, and the Phase 9
specialist-review branch measurably costs about +23% latency on the
tickets it fires for; a retrieval-quality score (0.800 precision / 0.639
recall) against a small, hand-labeled, self-authored eval set; and a
manual-vs-assisted human comparison that is built and ready but not yet
run.

What none of this proves: that this system saves time or improves
outcomes for a real support team with real customers at real volume. The
sample is historical CFPB complaint narratives, not this product's own
traffic (none exists yet); the eval set was written by the same person
who wrote the KB it's testing; and the one piece that would most directly
answer "does this actually help a human go faster" is the one piece that
still needs a human to sit down and run it. That's a narrower, more
specific gap than "no benchmarks exist" — which is exactly the point of
this phase.
