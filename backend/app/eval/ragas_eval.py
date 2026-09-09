"""RAGAS retrieval-quality eval (TRD: "One RAGAS eval run for real
retrieval-quality numbers" — real numbers, not a vibe).

Uses RAGAS's non-LLM context metrics: retrieved chunks are compared against
a hand-labeled reference document per query using string similarity, not an
LLM judge. That's a deliberate choice for this eval — it's deterministic,
fast, doesn't burn Groq quota just to grade retrieval, and retrieval quality
(did we fetch the right document?) is a well-defined ground-truth question
here, unlike generation quality, which would need a judge.

Usage: uv run python -m app.eval.ragas_eval
"""

import asyncio
import warnings
from dataclasses import dataclass

from ragas import SingleTurnSample

# The collections-based replacement ragas.metrics.collections points to
# doesn't include these non-LLM metrics yet as of ragas 0.4.3 — using the
# still-functional classic import and silencing the premature warning.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    from ragas.metrics import NonLLMContextPrecisionWithReference, NonLLMContextRecall

from sqlalchemy import or_, select

from app.db.base import SessionLocal
from app.models.kb import KbChunk, KbDocument
from app.retrieval.retrieve import retrieve


@dataclass(frozen=True)
class EvalExample:
    query: str
    category: str
    # Distinctive substring(s) of the KB document title(s) that should be
    # retrieved — matched with ILIKE, so no need to hand-type special
    # characters (em dashes, slashes) from the source titles here.
    expected_title_keywords: tuple[str, ...]


EVAL_SET: list[EvalExample] = [
    EvalExample(
        "My payment failed but I still see a pending charge, was I actually charged?",
        "payment_failure",
        ("Payment Failed But Funds Are Still Held",),
    ),
    EvalExample(
        "I was charged twice for the same order, can you fix the duplicate charge?",
        "payment_failure",
        ("Troubleshooting a Duplicate or Double Charge",),
    ),
    EvalExample(
        "Why do payments fail even when I have enough money in my account?",
        "payment_failure",
        ("Why Payments Fail",),
    ),
    EvalExample(
        "It's been over a week and my refund still hasn't shown up, what's going on?",
        "refund_delay",
        ("Why a Refund Might Be Delayed",),
    ),
    EvalExample(
        "How long does a refund normally take to process?",
        "refund_delay",
        ("Standard Refund Processing Timeline",),
    ),
    EvalExample(
        "Will my refund go back to my card or show up as store credit?",
        "refund_delay",
        ("Refund to Original Payment Method",),
    ),
    EvalExample(
        "How do I check the status of my refund?",
        "refund_delay",
        ("How to Check Refund Status",),
    ),
    EvalExample(
        "My account got locked and I don't know why, how do I get back in?",
        "account_lock",
        ("Common Reasons Accounts Get Locked", "How to Unlock Your Account"),
    ),
    EvalExample(
        "My account was locked for a compliance review, what do I need to do?",
        "account_lock",
        ("Account Locked for Compliance",),
    ),
    EvalExample(
        "How can I avoid getting locked out of my account again?",
        "account_lock",
        ("Preventing Future Account Lockouts",),
    ),
    EvalExample(
        "I want to dispute a transaction I don't recognize, how do I start?",
        "dispute",
        ("How to File a Transaction Dispute",),
    ),
    EvalExample(
        "How long does a dispute investigation usually take?",
        "dispute",
        ("Dispute Investigation Timeline",),
    ),
    EvalExample(
        "Do I get my money back immediately while a dispute is being investigated?",
        "dispute",
        ("Provisional Credit During a Dispute",),
    ),
    EvalExample(
        "What happens after a dispute is resolved, win or lose?",
        "dispute",
        ("Dispute Outcomes",),
    ),
    EvalExample(
        "How do I update the email address on my account?",
        "general_query",
        ("How to Update Your Account Information",),
    ),
    EvalExample(
        "The mobile app won't let me log in, what should I try?",
        "general_query",
        ("Mobile App and Login Troubleshooting",),
    ),
    EvalExample(
        "What are all these fees on my statement for?",
        "general_query",
        ("Understanding Your Statement and Fees",),
    ),
    EvalExample(
        "How fast does support usually respond and how do I reach them?",
        "general_query",
        ("How to Contact Support",),
    ),
]


async def _reference_contexts(db, keywords: tuple[str, ...]) -> list[str]:
    conditions = [KbDocument.title.ilike(f"%{kw}%") for kw in keywords]
    stmt = (
        select(KbChunk.content)
        .join(KbDocument, KbChunk.document_id == KbDocument.id)
        .where(or_(*conditions))
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all()]


async def main() -> None:
    precision_metric = NonLLMContextPrecisionWithReference()
    recall_metric = NonLLMContextRecall()

    precision_scores: list[float] = []
    recall_scores: list[float] = []

    async with SessionLocal() as db:
        for example in EVAL_SET:
            chunks = await retrieve(db, example.query, category=example.category, top_k=5)
            retrieved_contexts = [c.content for c in chunks]
            reference_contexts = await _reference_contexts(db, example.expected_title_keywords)

            sample = SingleTurnSample(
                user_input=example.query,
                retrieved_contexts=retrieved_contexts,
                reference_contexts=reference_contexts,
            )

            precision = await precision_metric.single_turn_ascore(sample)
            recall = await recall_metric.single_turn_ascore(sample)
            precision_scores.append(precision)
            recall_scores.append(recall)

            print(
                f"[{example.category:16}] precision={precision:.2f} recall={recall:.2f}  "
                f"{example.query[:55]!r}"
            )

    print()
    print(f"Mean context precision: {sum(precision_scores) / len(precision_scores):.3f}")
    print(f"Mean context recall:    {sum(recall_scores) / len(recall_scores):.3f}")


if __name__ == "__main__":
    asyncio.run(main())
