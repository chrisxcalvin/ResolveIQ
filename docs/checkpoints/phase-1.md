# Phase 1 checkpoint — known bug fixes

Two fixes, scoped exactly as specced. Nothing else touched.

---

## Fix 1: phone-number redaction gap

**What did you actually build?**

The PII redaction regex only matched full 10-digit US/Canada numbers with an
area code — `555-123-4567`. A bare local number with no area code —
`555-0142` — has a 3-4 digit shape, not 3-3-4, so it never matched and
passed straight through into the redacted text that gets sent to the LLM
and written to the audit log. I added a second alternative to the pattern
that matches the bare `XXX-XXXX` shape, and reordered redaction so card-number
matching runs *before* phone matching now.

**Why this approach, and what else did you consider?**

I considered pulling in a real phone-parsing library (`phonenumbers`) instead
of extending a hand-rolled regex. Ruled it out — this redaction layer isn't
trying to validate or normalize phone numbers, it's trying to catch anything
phone-shaped before it leaves the building, and a parsing library adds a
dependency and a false sense of correctness without actually solving the
harder problem (see the follow-up question below). Extending the existing
pattern was the smaller, more honest fix for what this actually needed to do.

The reorder wasn't optional, it was required by the fix: once the phone
pattern also matches a bare 3-4 digit shape, it can match a *slice* out of
the middle of a longer card number if card matching hasn't already claimed
it — e.g. a card written as groups of 4 has no exposure, but I wasn't
willing to bet every real-world card formatting convention avoids ever
producing an adjacent 3-then-4 split. Running card redaction first removes
the ambiguity instead of hoping the two patterns never collide.

**What's the failure mode if this were wrong or missing?**

A customer's real phone number rides along in the text that gets sent to
Groq's hosted API and gets written into `audit_log.detail`. In a fintech
context that's not a cosmetic miss, that's a PII exposure to a third party
and a permanent record of it in your own logs. And it fails *silently* —
there's no error, no warning, nothing distinguishes a ticket where redaction
worked from one where it didn't. The only way this was ever going to get
caught is exactly how it did get caught: someone manually reading a raw
redacted string and noticing a phone number still sitting in it.

**Sharp follow-up question, honestly answered:**

*"What about international numbers, extensions, or a phone number embedded
next to other digits?"* — Not handled. This is still a hand-authored regex
tuned to US/Canada-shaped numbers. A UK-formatted number, a number with an
extension (`x104`), or a phone number sitting directly adjacent to another
digit string wouldn't necessarily be caught correctly. That's a real,
acknowledged gap, not something this fix claims to solve — it closes the one
specific, confirmed hole (local 7-digit format), not the general problem of
"detect every phone number shape that could ever exist."

**Also found, deliberately not fixed here:** writing the redaction test
suite for this fix (`backend/tests/test_redaction.py`) surfaced a separate,
pre-existing issue — spaCy's NER tags an alphanumeric order ID like
`#A1092` as a `PERSON` entity and redacts it. That's unrelated to the phone
regex, was already there before this change, and is out of scope for a
phase scoped to exactly two named bugs. Logging it here so it doesn't get
lost — worth a follow-up.

---

## Fix 2: double-resolve race condition

**What did you actually build?**

`resolve_ticket` now takes a row lock on the ticket (`SELECT ... FOR
UPDATE`) as the very first thing it does, and checks whether the ticket's
status is already `resolved` or `escalated` before doing anything else. If
it is, the request gets rejected with a `409` and a clear message instead of
silently proceeding. Verified live: re-running `approve` against a ticket
that was already `resolved` now returns
`{"detail":"Ticket is already resolved — cannot resolve it again"}` with a
409, where before it would have gone through and overwritten the resolution
with no error to anyone.

**Why this approach, and what else did you consider?**

The obvious quick fix is just `if ticket.status in (...): raise` with no
locking. I didn't do that, because it's check-then-act — two requests
hitting the endpoint close together can both read `status == "drafted"`
before either one commits its write, and both would then proceed. That's the
exact bug, just moved one line later.

The real alternative worth naming is optimistic concurrency — a version
column, compare-and-swap on the update, reject if the version moved under
you. That's usually the better default for a row under real contention,
because it doesn't hold a lock and block a second request, it just fails
fast and lets the caller retry. I went with the pessimistic lock instead
specifically because a single ticket being resolved by two agents at once is
a rare event, not a hot path — the cost of a short block on that one row is
nothing compared to the simplicity of "the second request just waits, then
sees the true post-commit state." If this were a row under constant
contention, I'd make the opposite call.

**What's the failure mode if this were missing?**

Two agents open the same ticket. One clicks approve, the other clicks
escalate a few seconds later. Both succeed. You get two
`ticket_resolutions` rows and two `resolve`-type audit log entries for one
ticket, contradicting each other, and the ticket's final status is just
whichever write landed last — silently. Neither agent sees an error. The
only way anyone finds out is by noticing the audit log has two resolution
events on one ticket, after the fact.

**Sharp follow-up question, honestly answered:**

*"Have you actually load-tested this under real concurrency, not just
re-triggering it one request at a time?"* — No, and I want to be direct
about that rather than implying otherwise. What I verified today proves the
*state check* works correctly: an already-resolved ticket now gets rejected.
It does not prove the *lock* behaves correctly when two requests are
genuinely in flight at the same moment — that needs an actual concurrent
test (fire N requests at the same ticket simultaneously, confirm exactly one
succeeds and the rest get a clean 409, not a crash or a hang). That's
explicitly Phase 2's job, not skipped by accident.

---

## Also worth knowing: infrastructure hit a wall restarting today

Unrelated to either fix above: the whole local stack (Postgres/Redis in
WSL2, the API, the Celery worker) had gone down, almost certainly from a
machine restart between sessions. Postgres/Redis and the API came back up
cleanly. The Celery worker did not — it's failing to start with
`OSError: [WinError 1455] The paging file is too small for this operation
to complete`, while loading torch's CUDA DLLs. That's a Windows
virtual-memory/page-file limit, not a code issue, and it blocks anything
that needs the pipeline to actually run a ticket end-to-end (the cheap-tier
drafting model needs torch). The double-resolve fix above was verified
without it, using an already-resolved ticket from earlier testing, but this
needs fixing (increasing the Windows page file size) before Phase 2's
concurrency test can run for real.
