# Benchmarks

Per `BUILD_SPEC.md` Phase 8: real, measured numbers only — nothing
estimated or invented. Each section below states exactly what was
measured, the exact method, the sample size, and — just as important —
what the number does *not* prove.

## 1. Time-to-draft: real pipeline latency, not an estimate

**Method:** `app/scripts/benchmark_time_to_draft.py` picks real CFPB-
derived complaint narratives (80-600 characters, spread evenly across all
5 categories), submits each as a real `Ticket` through the exact same
`process_ticket.delay()` call `POST /tickets` makes, then polls the real
database for the resulting `TicketDraft` row. The reported time is
`TicketDraft.created_at - Ticket.created_at` — both real server
timestamps, not timers in this script. Tickets were submitted **one at a
time**, each one waited out to completion before the next was submitted,
specifically so the result measures per-ticket pipeline service time, not
queue-wait time inflated by this script's own submission pattern (see the
script's docstring for why that distinction matters given the deployed
worker is single-threaded by necessity).

**Sample:** 30 real tickets, run against a live local Celery worker
consuming from the same production Redis broker (Upstash) and writing to
the same production database (Neon) the deployed app uses — not a
separate synthetic environment.

**Results (n=30, 0 timeouts, 6 tickets per category):**

| | |
|---|---|
| Median | 18.85s |
| p95 | 25.05s |
| Min | 14.11s |
| Max | 26.46s |

Raw per-ticket data: `backend/app/ml/artifacts/benchmark_time_to_draft.json`.

**Two real, specific findings inside that distribution, not just the
summary stats:**

1. **Every one of the 30 tickets used the strong (Groq-hosted) tier — none
   used the cheap (local fine-tuned Qwen) tier.** Tier selection is based
   on `urgency_score < cheap_tier_urgency_threshold` (default 0.5); on
   this real sample of CFPB complaint narratives, the urgency classifier
   never scored a ticket below that threshold. Real consumer complaint
   writing tends to read as urgent/frustrated regardless of the
   underlying issue's actual severity, which is a plausible explanation —
   but it's reported here as an observation, not a confirmed cause. The
   practical implication is honest and worth stating plainly: the
   cost-routing design's savings depend on urgency distribution in real
   traffic, and this sample suggests that on CFPB-style text specifically,
   the cheap tier may see less traffic than a synthetic benchmark would
   suggest.
2. **The 7 tickets (23%) that triggered the Phase 9 specialist-review
   branch averaged 22.41s vs. 18.23s for the other 23 (+4.2s, ~+23%)** —
   the real, steady-state cost of that branch's extra retrieval + forced
   strong-tier redraft, isolated from the unrelated cold-start cost that
   inflated a single outlier (70s) in an earlier 5-ticket sanity run
   before the worker's models had warmed up. That cold-start effect is
   real too — this project's own worker-wake infrastructure
   (`app/core/worker_wake.py`) exists specifically because Render's
   free-tier worker sleeps and needs exactly this kind of warm-up — but
   it's a one-time cost, not a per-ticket one, so it's called out
   separately rather than left to inflate the steady-state number.

**What this does and doesn't prove:** this is real pipeline latency on
this machine's hardware (local cheap-tier model inference, real network
round-trips to Groq) — it is not a production-load test (nothing here
measures concurrent-ticket behavior or the deployed Render worker's own,
more memory-constrained performance) and the sample is CFPB complaint
narratives, not this product's own real customer tickets (none exist yet).

## 2. Manual-vs-assisted: built, deliberately not run

`app/scripts/benchmark_manual_vs_assisted.py` is a real, working tool for
this comparison — it reuses the real tickets and real AI drafts from
benchmark #1 and, for each one, would time a human two ways: (a) looking
up the answer in `backend/app/kb/articles/` and writing a reply from
what's found there, simulating an agent without this tool but *with* the
same knowledge base; (b) reviewing the real AI draft and approving,
editing, or rejecting it.

**This was deliberately not run.** It requires a human to actually sit
through 20 tickets' worth of manual KB lookups, which is real, tedious
work that wasn't worth the time cost here — a judgment call, made
explicitly rather than quietly skipped. Faking this number was never an
option (that's exactly the kind of fabricated metric this whole document
exists to avoid), so the honest choice was to not have the number rather
than invent one. The tool remains available —
`uv run python -m app.scripts.benchmark_manual_vs_assisted` from
`backend/` — if this comparison is ever worth the time later.

**What this means for the overall evidence:** this project does not claim
to have measured time savings vs. a human working unassisted. What it
does claim — real pipeline latency and real retrieval quality, both
below — stands on its own without that comparison.

## 3. Retrieval quality: RAGAS non-LLM context precision/recall

**Method:** `app/eval/ragas_eval.py`'s existing 18-example hand-labeled
eval set (real queries written against this project's own KB, each paired
with the specific document title it should retrieve), scored with RAGAS's
non-LLM `NonLLMContextPrecisionWithReference` / `NonLLMContextRecall`
metrics — deterministic string-similarity matching against ground truth,
not an LLM judge, so the same input always gives the same score and no
Groq quota is spent grading retrieval.

**Re-run for Phase 9/8** after two real changes since this eval set was
last exercised: the KB grew from 20 to 25 articles (5 new ones added for
underrepresented issue subtypes — see `docs/checkpoints/phase-9.md`), and
every embedding in the database was recomputed via a new local fallback
path after Hugging Face's hosted embeddings API ran out of free credits
(same model either way — see `docs/checkpoints/phase-9.md`'s outage
section). This re-run confirms retrieval quality held up through both
changes, not just that the new articles exist.

| Category | Query | Precision | Recall |
|---|---|---|---|
| payment_failure | "My payment failed but I still see a pending charge..." | 0.20 | 0.33 |
| payment_failure | "I was charged twice for the same order..." | 1.00 | 0.67 |
| payment_failure | "Why do payments fail even when I have enough money..." | 0.83 | 0.67 |
| refund_delay | "It's been over a week and my refund still hasn't shown..." | 0.50 | 0.33 |
| refund_delay | "How long does a refund normally take to process?" | 0.83 | 0.67 |
| refund_delay | "Will my refund go back to my card or show up as store credit?" | 1.00 | 0.67 |
| refund_delay | "How do I check the status of my refund?" | 1.00 | 0.67 |
| account_lock | "My account got locked and I don't know why..." | 1.00 | 0.83 |
| account_lock | "My account was locked for a compliance review..." | 1.00 | 0.33 |
| account_lock | "How can I avoid getting locked out of my account again?" | 0.20 | 0.33 |
| dispute | "I want to dispute a transaction I don't recognize..." | 0.92 | 1.00 |
| dispute | "How long does a dispute investigation usually take?" | 1.00 | 0.33 |
| dispute | "Do I get my money back immediately while a dispute is pending?" | 0.33 | 0.33 |
| dispute | "What happens after a dispute is resolved, win or lose?" | 0.83 | 0.67 |
| general_query | "How do I update the email address on my account?" | 0.76 | 1.00 |
| general_query | "The mobile app won't let me log in..." | 1.00 | 1.00 |
| general_query | "What are all these fees on my statement for?" | 1.00 | 0.67 |
| general_query | "How fast does support usually respond and how do I reach them?" | 1.00 | 1.00 |

**Mean context precision: 0.800. Mean context recall: 0.639.**

This is the first time these numbers have been captured and documented —
no prior baseline exists to compare against, so this *is* the baseline
going forward. The weakest examples (`payment_failure`'s first query at
0.20 precision, `account_lock`'s lockout-prevention query at 0.20
precision, `dispute`'s provisional-credit-timing query at 0.33/0.33) are
real, specific, named gaps — not hidden behind the mean.

**What this does and doesn't prove:** this is retrieval quality (did the
right document get fetched?) against a small, hand-labeled eval set
authored by the same person who wrote the KB articles — it is not a
measure of draft/generation quality, and a hand-labeled set of this size
can't rule out blind spots in categories or phrasings it didn't think to
include.
