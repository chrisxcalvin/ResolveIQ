# Phase 2 checkpoint — testing

## What did you actually build?

A `pytest` suite (44 tests, all passing) covering four things: the
redaction patterns from Phase 1, the decision-agent thresholds, the
confidence formula and zero-chunks refusal path, and the retrieval-boost
math including its clamp boundaries — plus an HTTP-level test of the
double-resolve guard, hitting the real FastAPI app through an in-process
ASGI client against a disposable `resolveiq_test` Postgres database.
Separately, a live concurrency test: 10 simultaneous ticket submissions
against the actually-running API/worker/Postgres/Redis stack, plus 3 runs
of two simultaneous resolve requests racing on the same ticket.

## Why this approach, and what else did you consider?

For the DB-backed tests, the alternative was SQLite. Ruled out — several
models use a real pgvector `vector` column, which SQLite can't represent,
so a SQLite suite would be testing against a different database than the
one that actually runs. Used the same WSL2 Postgres instance instead, with
a separate `resolveiq_test` database.

For test isolation, the alternative to a transactional rollback pattern
was cleanup code at the end of each test (delete what you inserted).
Rejected — that's error-prone and gets worse as more tests touch more
tables. Instead each test runs inside one outer transaction that's rolled
back afterward, using SQLAlchemy's `join_transaction_mode="create_savepoint"`
specifically because `resolve_ticket` itself calls `db.commit()` — without
that setting, the endpoint's own commit would end the outer transaction
early and the rollback at the end of the test would have nothing left to
undo.

For the concurrency test, the alternative was a synthetic unit test that
mocks the lock and asserts it was called. Rejected outright — that proves
the code calls `SELECT ... FOR UPDATE`, not that it actually works under
concurrent load. Fired real simultaneous requests at the real stack
instead.

## What's the failure mode if this were wrong or missing?

Same as before this suite existed: every bug in Phase 1 was found by
manually poking at a running system, not by a test catching it. Without
this suite, a future change to the redaction patterns, the confidence
formula, or the boost math could silently reintroduce exactly those bugs,
and nothing would flag it until someone noticed by hand again — which,
per this whole project's history so far, has taken anywhere from
immediately to unnoticed-for-a-month (see the Groq model deprecation).

## What's the one follow-up question a sharp interviewer would ask next, and what's the honest answer?

*"Your event loop is session-scoped for the whole test run — doesn't that
mean tests aren't actually isolated from each other at the asyncio level,
only at the database level?"* — Correct, and worth being direct about.
`asyncio_default_fixture_loop_scope = "session"` was required to fix a
real bug (see below), but it does mean all 44 tests share one event loop
and one `_test_engine` connection pool for the whole run. Database state
is genuinely isolated (transactional rollback per test), but if a test
ever leaked an unawaited task or left a connection in a bad state, that
could theoretically bleed into the next test via the shared loop. Not
something the suite currently guards against — worth adding a fixture
that asserts no dangling tasks after each test if this suite grows much
further.

---

## A real bug the test suite itself surfaced (not application code — the harness)

First run of `test_retrieval_boost.py` failed 9 of 10 tests with
`sqlalchemy.exc.InterfaceError: cannot perform operation: another
operation is in progress` on `SAVEPOINT sa_savepoint_1`. Root cause:
pytest-asyncio's default fixture-loop scope is per-test-function, but the
test engine (`_test_engine` in `conftest.py`) is a module-level singleton
created once. Every test after the first was trying to reuse pooled
asyncpg connections that belonged to a *different, already-closed* event
loop — a known, classic asyncpg/SQLAlchemy-async gotcha, not a bug in the
code under test. Fixed by setting
`asyncio_default_fixture_loop_scope = "session"` (and
`asyncio_default_test_loop_scope = "session"`) in `pyproject.toml`, so the
whole test run shares one event loop, matching the single shared engine.
Flagging this here rather than treating it as boring test infrastructure
plumbing: it's the kind of thing that silently produces false failures
that look like application bugs if you don't trace them back to the actual
cause.

---

## Concurrency test result

**What N=10 proves:** 10 ticket submissions fired genuinely simultaneously
(`asyncio.gather`, not a loop) against the live API all returned `201` in
2.39s wall-clock combined. All 10 were picked up by the Celery worker,
correctly classified (`payment_failure`), drafted, and reached a terminal
status within 16 seconds total — zero dropped tickets, zero ID collisions,
zero worker crashes or deadlocks.

**What N=10 does NOT prove:** the worker runs with `--pool=solo`
(required on Windows), meaning it processes exactly one task at a time,
not in parallel — the ~1.6s-per-ticket pace visible in the per-ticket
timings is sequential draining of a queue, not concurrent execution inside
the worker. This test proves the *API and database* handle concurrent
write load correctly (10 simultaneous `INSERT`s into `tickets`/`customers`
with no corruption or collision), and that the queue-and-drain mechanism
via Redis/Celery doesn't lose or duplicate work under a burst. It does
**not** prove the system holds up under sustained high throughput, under a
multi-process/multi-worker deployment, or at N significantly larger than
10 — those would need a real load-testing tool (locust, k6) and a
non-solo worker pool, neither of which this does.

**Bonus, closing a gap Phase 1 explicitly flagged as untested:** Phase 1's
checkpoint said the double-resolve lock had only been verified
*sequentially* (re-resolve after the first request already committed),
not under genuine concurrency. Fixed that gap here — built
`tests/concurrency_check.py` (a real, documented, reusable tool, not a
throwaway script) that fires N simultaneous resolve requests
(alternating approve/escalate) at the *same* drafted ticket. At N=10:
**exactly 1 got `200`, the other 9 got a clean `409`** — the row lock,
not just the status check, correctly serialized ten genuinely concurrent
requests down to one winner. That's the harder, more meaningful proof the
earlier checkpoint said was still owed, and it held up at 10-way
contention, not just 2.
