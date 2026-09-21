# Phase 6 checkpoint — UI overhaul

This phase is a design-decision phase, not a bug-fix phase, so most of what
follows defends *why* the console looks the way it does rather than
describing what it looks like — per the build spec's own instruction for
this checkpoint. One real bug did turn up during verification, documented
in its own section below, because it's the kind of thing that would have
silently undermined every other decision in this phase if it had gone
unnoticed.

## Three-panel console, not a chat UI

**What did you actually build?** A fixed three-column layout —
queue (left) → ticket + pipeline trace (center) → inspectable context
(right) — replacing what was effectively two separate, disconnected pages
(`/queue` as a table, `/tickets/[id]` as a standalone detail view). Both
routes now render the same `ConsoleView` component
(`frontend/src/components/console/console-view.tsx`), just with a
different `selectedTicketId`, so the queue and the open ticket are always
visible together.

**Why this approach, and what else did you consider?** A chat-style
interface (ticket on one side, an AI "assistant" bubble replying on the
other) was the obvious default — it's what most AI-product UIs default to,
and it would have been less work to build. Rejected it because it's the
wrong mental model for this product. A support agent working a queue under
breach-risk pressure isn't having a conversation with the AI; they're
auditing a decision the AI already made and either accepting, correcting,
or overriding it. A chat thread implies back-and-forth exploration; a
console implies "here's the queue, here's the case, here's the evidence,
decide." The three-panel layout makes that literal: you can never look at
a ticket without also seeing where it sits in the queue and what evidence
backed the draft, because those three things are the actual unit of an
agent's decision, not three separate concerns to tab between.

**What's the failure mode if this were wrong or missing?** A chat UI would
have made the AI's reasoning something the agent has to scroll up and find
in prior turns, exactly the failure mode this product is supposed to fix
relative to a black-box AI draft. The whole pitch is "reasoning is
inspectable" — burying that reasoning back inside a conversational log
would have quietly undone the product's own differentiator while still
technically satisfying "there's an AI draft on screen."

**Sharp follow-up question, honestly answered:** *"Doesn't a fixed
three-column layout break on anything narrower than a wide monitor?"* —
Yes, partially. Below `md` breakpoint the panels stack vertically instead
of sitting side by side (`flex-col md:flex-row` in `ConsoleView`), which
keeps it usable but loses the "everything visible at once" property that's
the actual point of the layout. This is a real trade-off, not hidden: the
console is designed for the environment a support agent actually works in
(a desk, a real monitor), and it degrades rather than being redesigned for
phone-width use, because a phone-width triage console isn't a real use
case for this product.

---

## The pipeline trace is shown, not hidden behind a status badge

**What did you actually build?** A horizontal six-stage trace
(`frontend/src/components/pipeline-trace.tsx`) — redacted → classified →
scored → retrieved → drafted → routed — rendered permanently in the
ticket panel, not tucked behind a tooltip or a "details" toggle. It's used
in two different states: a static done/pending binary on the ticket-detail
view, and a done/active/pending state on `/tickets/new` driven by real
polling data rather than a simulated progress bar.

That second state turned out to have a real wrinkle, only visible once a
real ticket was watched end to end through a locally running worker
(below): `app/tasks.py` runs the entire LangGraph pipeline in memory and
writes every field — redaction, category, scores, draft, decision — in
one `db.commit()` at the very end, not incrementally per stage. So what
the frontend's polling actually observes is exactly two states, not a
smooth six-step reveal: stage one ("Redacted") pulsing while everything
else sits pending, for the ticket's entire processing time, then all six
flipping to done in the same poll tick. That's not a bug in the frontend
— it's an honest reflection of a backend that genuinely has no
intermediate checkpoints to report. Adding real per-stage commits would
fix it, but that's a pipeline-architecture change, out of scope for a UI
phase, and not something to bolt on quietly just to make the animation
look more granular than the backend actually is.

**Why this approach, and what else did you consider?** Could have shown
just a status badge ("Drafted") and left the six-stage breakdown as
something you open on demand. Rejected because the six stages *are* the
inspectability the product is selling — a status badge tells you the
pipeline finished, not what it did. Keeping the trace permanently visible
costs vertical space in the center panel; that cost was accepted
deliberately because hiding it behind a click is exactly the "AI as
black box" pattern this product exists to move away from.

**What's the failure mode if this were wrong or missing?** An agent
reviewing a low-confidence, specialist-flagged draft would have no fast
way to tell *which* stage the system was least sure about — bad
classification, weak retrieval, or a genuinely hard case — without the
trace's per-stage detail strings (category name, breach-risk number,
source count, confidence, routing outcome). Without it, the confidence
number on its own is a single opaque float, which is the exact complaint
the design spec opens with.

**Sharp follow-up question, honestly answered:** *"The static ticket-detail
view only ever shows all-done or all-pending — isn't that a fake trace,
since it can't show a ticket half-processed?"* — Correct, and worth being
direct about it rather than dressing it up as more granular than it is.
The backend pipeline genuinely doesn't persist intermediate state anywhere
a page load could read it back — it's one synchronous LangGraph run per
ticket, not a resumable job with per-stage checkpoints. The honest version
of "show the trace" for an already-completed ticket really is binary. The
`/tickets/new` page is where the trace earns its keep, because that's the
one place real incremental state exists to show.

---

## Monospace is a data rule, not a font choice

**What did you actually build?** IBM Plex Mono is applied through exactly
one mechanism, a `.font-data` utility class (`frontend/src/app/globals.css`),
and that class is only ever put on actual data values — ticket IDs,
timestamps, confidence percentages, breach-risk numbers, the JSON blob in
the audit log. Every label, button, and heading stays on Archivo. Nothing
in this phase reaches for `font-mono` directly outside that one utility.

**Why this approach, and what else did you consider?** The easy version of
"give this a terminal feel" is to just set the whole UI in a monospace
font, or monospace specific components (buttons, badges) for visual
flavor. Rejected both — the spec is explicit that monospace marks data,
not decoration, and conflating the two would make the one real signal
(this is a number that was computed, not written) disappear into general
styling noise. `.font-data` also sets `font-variant-numeric: tabular-nums`,
which is the actual functional payoff: confidence percentages and
timestamps in the queue table line up in a fixed-width column instead of
jittering as digits change width, which matters for a table an agent is
scanning quickly, not just for looks.

**What's the failure mode if this were wrong or missing?** If monospace
were applied more broadly (e.g., to every badge or every button), an agent
scanning the console would lose the one visual cue that currently means
"this is a raw system output, not authored copy" — the distinction between
"Escalate" (a label a person wrote) and `0.29` (a number the pipeline
computed) would flatten out, undermining exactly the inspectability the
rest of this phase is built around.

**Sharp follow-up question, honestly answered:** *"How would you catch a
future PR that puts `.font-data` on a label by mistake?"* — Nothing
automated does today; it's enforced by convention and this checkpoint, not
by a lint rule. A cheap real guard would be an ESLint rule banning
`font-data` inside `<button>`/label-ish elements, but that's speculative
tooling for a one-file-deep pattern right now — not built, because it
would be solving a problem that hasn't happened yet.

---

## Confidence is shown as two components, not one blended number

**What did you actually build?** Backend instrumentation
(`backend/app/tasks.py`) now captures `avg_retrieval_similarity` (mean
similarity across retrieved chunks) alongside the existing
`category_confidence`, persisted into the same `audit_log.detail` JSONB
snapshot pattern the "drafted" event already used for
`specialist_flagged`/`decision_reason`. The right-hand context panel shows
both terms with their actual weights (retrieval × 0.6, category × 0.4)
next to the final computed confidence, instead of just the final number.

**Why this approach, and what else did you consider?** Considered
back-solving the two components algebraically from the final clamped
confidence value already stored on the ticket — rejected, because the
confidence score is clamped, and back-solving through a clamp boundary
produces numbers that look precise but are wrong exactly when a value was
near 0 or 1. Properly instrumenting the pipeline to capture the real
component at the moment it's computed was more backend work (a new field
threaded through `tasks.py` → `schemas/ticket.py` → the `/tickets/{id}`
route → the frontend type) but means the number on screen is the number
that was actually computed, not a reconstruction.

**What's the failure mode if this were wrong or missing?** A single
blended confidence number can't distinguish "the classifier was unsure
what category this even was" from "the classifier was confident but
retrieval found nothing relevant to ground a reply on" — two failure modes
that call for different agent responses (re-read the raw message vs. trust
the category but write the reply from scratch). Collapsing them into one
float, which is what the UI did before this phase, hides that distinction
from the person who most needs it.

**Sharp follow-up question, honestly answered:** *"What does the panel
show for tickets drafted before this instrumentation existed?"* — Exactly
what actually happened when this was checked against real data during
this phase: `avg_retrieval_similarity: null` for an older ticket whose
audit log predates the new field, rendered as `—` in the breakdown rather
than a misleading `0` or a crash. Old tickets simply don't have retroactive
component data; nothing was backfilled, and the UI is honest about that
gap instead of hiding it.

---

## A real bug found during verification: a stale backend process

**What did you actually build?** Nothing new here — this is a bug found
while checking the confidence-breakdown work above against live data, not
a design decision, but it's worth recording because it would have quietly
invalidated this entire phase's backend verification if it had gone
unnoticed.

**What happened?** Fetched a real ticket from the local API to confirm
`category_confidence`/`avg_retrieval_similarity` were actually flowing
through end to end. The response was missing both fields entirely — not
`null`, just absent, even for `specialist_flagged`/`decision_reason` which
share the exact same code path and *did* show up correctly as `false` and
`null` respectively. That asymmetry (some fields from the same block
present, two specific newer ones silently gone) was the tell that this
wasn't a code bug — the two fields were provably absent from the running
process's schema, despite being present on disk in
`backend/app/schemas/ticket.py`.

Root cause: two duplicate `uv run uvicorn --reload` background processes
had been started against the same port earlier in the session. Only one
ever actually bound to 8000, and its `--reload` watcher had logged
"detected changes... Reloading..." for an edited file but never logged
the corresponding "Started server process" line that a successful reload
always produces — the reload had silently stalled, leaving a process
running code from before this phase's schema changes were made, serving
requests normally with no error anywhere in its logs.

**What's the failure mode if this were wrong or missing?** Exactly what
was almost shipped: a checkpoint claiming the confidence-breakdown feature
was "verified against live data" when the live data was actually coming
from stale code that didn't have the feature. The API returned `200` the
entire time — nothing about this failure looks like a failure from the
outside, which is the dangerous part.

**Fix and re-verification:** Killed both duplicate processes, confirmed
port 8000 was free, started one clean process, and re-fetched the same
ticket — `category_confidence` and `avg_retrieval_similarity` both
appeared correctly (`0.378` and `null` respectively, the `null` being
correct because that ticket's draft cited zero source chunks).

**Sharp follow-up question, honestly answered:** *"How would you catch
this faster next time, instead of noticing an asymmetry between two
fields by luck?"* — Check the reload log for a matching "Started server
process" line after every edit to a file the running dev server depends
on, not just the "detected changes" line — a reload that starts but never
completes is silent otherwise. More generally: a `200` response is
evidence the server is up, not evidence it's running the code currently on
disk; those are different claims and this phase conflated them once.

---

## Status at time of writing

**Verified:** TypeScript compiles clean (`tsc --noEmit`, zero errors)
across every touched file. ESLint passes clean on every touched file,
including two real issues the linter caught during this phase — a
render-time mutation in `/tickets/new`'s stage-derivation logic, and a
`setState` call inside an effect in the console component that turned out
to be unnecessary once the component is remounted via `key` on ticket
change rather than manually resetting its own state. Both fixed, not
suppressed. Every touched route (`/queue`, `/login`, `/tickets/new`,
`/admin/audit-log`, `/tickets/[id]`) returns `200` with no error-boundary
text against the local dev server. The confidence-breakdown backend fields
were confirmed against real ticket data in the local Postgres database
after fixing the stale-process bug above, not just against the schema on
disk.

**A real browser check, and three real findings it caught.** This
environment has no built-in browser-automation tool, so one was installed
specifically for this — Playwright, downloaded into a scratch directory
outside the project (not added as a project dependency, since nothing in
the shipped app needs it), scripted to log in as a real seeded user and
screenshot all five touched routes with real data from the local database.
Worth doing rather than skipping, because it caught exactly the class of
bug static checks can't: three real violations of this phase's own design
spec that every type-check, lint pass, and route smoke test had missed
because they're not type errors or crashes, they're a page that renders
fine and is wrong anyway.

1. Pipeline-trace stage labels and five section headers ("Customer
   message," "AI draft reply," "Confidence breakdown," etc.) were styled
   with `uppercase tracking-wide` — the literal "all-caps eyebrow label"
   pattern this same checkpoint document's design spec explicitly bans as
   a generic-AI-UI tell, sitting undetected in code that otherwise looked
   like ordinary label styling.
2. Two spots joined a customer identifier and a channel, and a ticket
   count and a sort description, with a "·" middle dot — the other
   explicitly banned pattern, also invisible to anything short of reading
   the rendered text.
3. The queue panel's subtitle ("N tickets, sorted by breach risk") was
   set in `.font-data` (IBM Plex Mono) — directly contradicting this
   checkpoint's own "monospace is a data rule, not a font choice" section
   above, on a plain descriptive sentence that isn't a data value at all.

All three fixed (eyebrow labels back to sentence case with no transform,
middle dots replaced with a channel badge and a comma respectively,
the subtitle moved to Archivo with only the numeral itself kept in
`.font-data`), re-typechecked, re-linted, and re-screenshotted to confirm
the fixes actually rendered — not just that the diff looked right.

**The live pulse, watched end to end.** The port-6379 block from Phase 5
was specific to the network in use at the time — once that changed mid-
session, a raw TCP test to Upstash succeeded, so a local Celery worker was
started against the real broker and a real ticket was submitted through
`/tickets/new` and polled to completion: a real Hugging Face embedding
call, a real Groq draft call, both visible in the worker's own logs, and
the finished trace rendering all six stages with correct detail strings
(`breach risk 0.13`, `2 source(s) cited`, `confidence 46%`, `standard`
routing) against a real 14.4-second run. This is also what surfaced the
atomic-commit finding written into the section above — watching the real
poll sequence, not just reading the code, is what showed the trace only
ever has two observable states instead of a smooth six-step reveal.

**Not yet done:** committing and pushing this phase's changes, and
confirming the Vercel deploy picks up the new design the same way Phase 5
verified the worker fix. The local Celery worker, uvicorn, and Next.js dev
server are still running for any further manual checking before that.
