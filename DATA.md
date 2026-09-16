# Data provenance

No public dataset of real fintech support tickets exists. Every dataset in
this project is real, synthetic, or authored — this file says which,
honestly, for each one. Where a number could be misread as a
production-readiness claim, it isn't one; see the caveat next to it.

## Real data

### Category classifier training data

**Source**: [CFPB Consumer Complaint
Database](https://www.consumerfinance.gov/data-research/consumer-complaints/)
— a real, public, continuously-updated US government dataset of consumer
complaints against banks, credit card issuers, lenders, and money-transfer
services. ~17.6M complaints total, ~3.85M carry a free-text narrative
(`complaint_what_happened`). Narratives arrive pre-redacted by the CFPB
(`XXXX` placeholders for names/dates), which is a reasonable analog for the
kind of already-somewhat-sanitized text a real support pipeline sees.

**How it's used**: `app/ml/cfpb_data.py` fetches narratives per CFPB
`issue` category, mapped onto ResolveIQ's 5 ticket categories (mapping
table lives in that file, keyed on `issue` rather than `product` — issue
describes what went wrong, which is what our categories are actually
about). 9,858 narratives survived after dropping exact and near-duplicates
(cosine similarity >= 0.9 against a TF-IDF vectorization — CFPB contains
complaints that are copy-pasted near-verbatim from advocacy sites, which
would otherwise land on both sides of the train/test split and quietly
inflate the score).

**Result**: `app/ml/train_classifier.py` reports a genuine held-out
accuracy of **0.773** (7,886 train / 1,972 test, stratified split, near-dup
leakage check: 1 of 1,972 test rows flagged, highest similarity 0.930 —
effectively clean). This replaces a synthetic-template classifier that
reported 1.000 — a number that measured template memorization, not
category understanding (see "What changed" below).

**Known limitation of the mapping itself**: CFPB has no clean "refund"
category — `refund_delay` is mapped from the closest available issues
(`Money was not available when promised`, loan-approved-but-no-funds
variants, lost/stolen refunds or money orders), which is a real but
imperfect proxy. `account_lock` similarly leans on account-closing and
wallet-access issues rather than a direct "locked out" complaint type. The
0.773 accuracy reflects these imperfect category boundaries as much as
model capability — a cleaner taxonomy alignment would likely move the
number, in either direction.

## Synthetic (real ground truth doesn't exist, kept honest about it)

### SLA breach-risk classifier

**Source**: `app/ml/breach_risk_data.py` — 1,500 synthetic examples
generated from a hand-written weighted rule (ticket age, category risk
weight, urgency score, queue depth → a score, thresholded, then 5% label
noise injected).

**Why this stays synthetic, deliberately, not as a shortcut**: there is no
public dataset of real SLA breach outcomes for fintech support tickets —
this isn't something CFPB or any other public source tracks. Held-out
accuracy (0.933) measures whether the classifier can recover the
hand-written rule it was trained to approximate, not whether the rule
itself predicts real breach risk. It's a demonstration of the mechanism
(rule → label → trained model → queue reordering), not a claim about real
SLA behavior.

### Urgency classifier

**Source**: `app/ml/data.py` — 282 template-generated examples (still
synthetic, unlike the category classifier above).

**Why urgency didn't move to CFPB**: CFPB complaints carry no urgency
label of any kind, and inventing one (e.g. from complaint age or company
response time) would produce another fabricated ground truth — arguably
worse than being upfront that this classifier is still template-trained.
Its held-out accuracy (1.000) is explicitly **not** a generalization
estimate for the same reason the old category number wasn't: template
rows share a phrasing skeleton across the train/test split. It's a
pipeline-correctness check, not a claim about real-world urgency
detection.

## Authored (legitimate to author, not a shortcut)

### Knowledge base articles

20 hand-written help articles (`app/kb/articles/`), 4 per category, 60
embedded chunks. Authoring a company's own KB content is exactly what a
real company would do — this isn't a gap to fill with public data, unlike
the classifier training data was. Worth knowing: 60 chunks is thin for a
retrieval eval (RAGAS: 0.79 precision / 0.69 recall on an 18-example
hand-labelled set) — expanding this corpus would be the highest-leverage
next step for retrieval quality specifically.

### Fine-tuning triples (cheap-tier drafting model)

80 hand-written (ticket, retrieved-context, grounded-reply) triples
(`app/ml/finetune/data.py`). The reply side is legitimately authored —
someone has to write what a good grounded answer looks like. The ticket
side could reasonably be swapped for real CFPB phrasing in a future pass
(the build spec calls this out as optional); not done in this pass, so the
cheap-tier model has only ever seen synthetic ticket phrasing during
fine-tuning, not real complaint language.

## What changed in Phase 3, and why the honest number matters more than a good one

The category classifier's held-out accuracy dropped from a reported 1.000
to a genuine 0.773. That's the point, not a regression. The old number came
from template-generated data where train and test rows shared a phrasing
skeleton — the classifier had learned the templates, not the task. 0.773
on real, independently-written complaint narratives, with a near-duplicate
leakage check confirming the split is actually clean, is a number that
means something: it reflects genuine category confusion on real text (see
the confusion matrix printed by `train_classifier.py` — `general_query` and
`payment_failure` are the most commonly confused pair, which tracks with
how often a real complaint mentions both a fee and a failed payment in the
same narrative).
