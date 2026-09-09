"""Picks the drafting tier by urgency_score and computes a shared, numeric
confidence estimate (not either model's self-report).
"""

from dataclasses import dataclass

from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.drafting.cheap_tier import draft_cheap_tier
from app.drafting.strong_tier import draft_strong_tier
from app.retrieval.retrieve import RetrievedChunk

UNAVAILABLE_MESSAGE = "AI draft unavailable, manual response needed."

_retry = retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))


@dataclass(frozen=True)
class DraftResult:
    draft_text: str
    source_chunk_ids: list[str]
    confidence: float
    tier: str  # "cheap", "strong", "none", or "unavailable"


def _estimate_confidence(chunks: list[RetrievedChunk], category_confidence: float) -> float:
    if not chunks:
        return 0.0
    avg_similarity = sum(c.similarity for c in chunks) / len(chunks)
    return max(0.0, min(1.0, 0.6 * avg_similarity + 0.4 * category_confidence))


@_retry
def _draft_cheap_tier(ticket_text: str, chunks: list[RetrievedChunk]):
    context = "\n\n".join(f"({c.document_title}): {c.content}" for c in chunks)
    return draft_cheap_tier(ticket_text, context)


@_retry
def _draft_strong_tier(ticket_text: str, chunks: list[RetrievedChunk], customer_history: str):
    return draft_strong_tier(ticket_text, chunks, customer_history)


def draft(
    ticket_text: str,
    chunks: list[RetrievedChunk],
    urgency_score: float,
    category_confidence: float,
    customer_history: str = "",
) -> DraftResult:
    if not chunks:
        # Never fabricate an answer when retrieval found nothing relevant
        # (App Flow failure paths).
        return DraftResult(
            draft_text="No relevant knowledge base information was found for this ticket.",
            source_chunk_ids=[],
            confidence=0.0,
            tier="none",
        )

    confidence = _estimate_confidence(chunks, category_confidence)

    try:
        if urgency_score < settings.cheap_tier_urgency_threshold:
            result = _draft_cheap_tier(ticket_text, chunks)
            return DraftResult(
                draft_text=result.reply,
                source_chunk_ids=[c.chunk_id for c in chunks],
                confidence=confidence,
                tier="cheap",
            )

        result = _draft_strong_tier(ticket_text, chunks, customer_history)
        return DraftResult(
            draft_text=result.reply,
            source_chunk_ids=result.source_chunk_ids,
            confidence=confidence,
            tier="strong",
        )
    except Exception:
        return DraftResult(
            draft_text=UNAVAILABLE_MESSAGE,
            source_chunk_ids=[],
            confidence=0.0,
            tier="unavailable",
        )
