# Phase 3 checkpoint — real data

## What did you actually build?

A fetcher for the CFPB Consumer Complaint Database (`app/ml/cfpb_data.py`)
that pulls real consumer complaint narratives, maps them onto ResolveIQ's
5 categories by their own CFPB `issue` field, and retrained the category
classifier on ~9,858 real complaints instead of hand-written templates.
Held-out accuracy dropped from a reported 1.000 to a real **0.773**. The
urgency and SLA breach-risk classifiers stay synthetic, deliberately, with
the reasoning documented in `DATA.md`.

## Why this approach, and what else did you consider?

The obvious first move with a public search API is to page through results
for a large sample. I tried that — request `frm`/`from`/`offset`/`page`
params for pagination — and every one of them was silently ignored by the
API; three different pages at `frm=0/100/200` returned the *identical*
first 100 rows. `search_after` (the modern Elasticsearch cursor pattern)
rejected every cursor format I tried with a `424`. Rather than working
around a broken pagination contract, I tested how large a single `size`
request could go and found it works cleanly up to at least 5,000 unique
rows in one call — so the fetcher does one large request per issue instead
of paging, which is simpler and, more importantly, actually correct
instead of silently wrong.

The other real decision was where the category label comes from. My first
version trusted the `issue` query parameter I'd requested and labelled
every returned row with it. That's the same mistake the ContractWatch
reference report's author made with keyword matching — trusting what you
asked for instead of what you got back. Fixed it to read each row's *own*
`issue` field from the response and only keep rows where it matches
exactly, dropping anything else. Costs nothing when the filter behaves (it
does — 0 mismatches in the actual run) and eliminates an entire class of
silent mislabelling if it ever doesn't.

## What's the failure mode if this were wrong or missing?

Two distinct failure modes, both real, both caught before they shipped:

1. **The pagination bug**, if unnoticed, would have meant every "different"
   page was actually the same rows again. Concretely, an early run of this
   exact bug produced 333 "different" complaints for an issue
   (`Lost or stolen refund`) that genuinely has 6 total narratives in all
   of CFPB — and worse, 3,561 duplicate complaint IDs where the *same*
   real complaint got recorded under multiple different category labels
   because each request-with-ignored-pagination returned overlapping data
   labelled by whatever issue that request happened to be for. That's
   training data corruption that would have been invisible in the
   accuracy number alone — a classifier can score fine while being trained
   on the same complaint contradicting itself across two categories.
2. **A near-duplicate leakage gap in the initial split** — 45 of 1,994 test
   rows had a near-exact match in training (one at cosine similarity
   1.000), inflating the first honest-looking number (0.782) slightly
   above what it should be. A TF-IDF near-duplicate filter (documented in
   `train_classifier.py`) now drops those before splitting; the check
   afterward found only 1 residual near-duplicate at 0.930 similarity —
   effectively clean.

Neither of these would have thrown an error. Both would have looked like
a working pipeline producing a plausible number.

## What's the one follow-up question a sharp interviewer would ask next, and what's the honest answer?

*"0.773 on 5 classes — is that actually good?"* — On its own, no strong
claim either way; it needs a baseline. A random classifier over 5
balanced classes scores 0.20, so 0.773 is well above chance, and the
confusion matrix shows the errors are concentrated where you'd expect
(`general_query` and `payment_failure` are the most confused pair — real
complaints often mention both a fee *and* a failed payment in the same
narrative, which is a genuine category-boundary ambiguity, not a model
failure). The more honest caveat is the one in `DATA.md`: CFPB has no
clean "refund_delay" or "account_lock" category, so part of what the model
is being scored against is *my own* imperfect mapping of CFPB's taxonomy
onto ResolveIQ's, not a ground truth CFPB itself asserts. The number is
real and the split is clean, but it's bounded by how well 5 categories I
chose actually carve up complaints CFPB never organized that way to begin
with.
