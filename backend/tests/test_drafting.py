"""Phase 2: the confidence formula and the zero-chunks refusal path
(app/drafting/draft.py). Both are pure/no-model-call paths — no DB, no
Groq/local-model calls needed to test either.
"""

from app.drafting.draft import UNAVAILABLE_MESSAGE, _estimate_confidence, draft
from app.retrieval.retrieve import RetrievedChunk


def _chunk(similarity: float) -> RetrievedChunk:
    return RetrievedChunk(chunk_id="c1", document_title="doc", content="x", similarity=similarity)


# --- confidence formula: 0.6 * avg(similarity) + 0.4 * category_confidence --

def test_confidence_formula_exact_value():
    chunks = [_chunk(0.8), _chunk(0.6)]  # avg similarity = 0.7
    result = _estimate_confidence(chunks, category_confidence=0.5)
    assert abs(result - (0.6 * 0.7 + 0.4 * 0.5)) < 1e-9


def test_confidence_averages_across_multiple_chunks():
    chunks = [_chunk(1.0), _chunk(0.0), _chunk(0.5)]  # avg = 0.5
    result = _estimate_confidence(chunks, category_confidence=1.0)
    assert abs(result - (0.6 * 0.5 + 0.4 * 1.0)) < 1e-9


def test_confidence_empty_chunks_is_zero():
    assert _estimate_confidence([], category_confidence=0.9) == 0.0


def test_confidence_clamped_to_one_even_if_formula_would_exceed_it():
    """similarity/category_confidence are meant to be 0-1, but the clamp
    should hold even if a caller passes something out of range."""
    chunks = [_chunk(2.0)]
    result = _estimate_confidence(chunks, category_confidence=2.0)
    assert result == 1.0


def test_confidence_clamped_to_zero_even_if_formula_would_go_negative():
    chunks = [_chunk(-1.0)]
    result = _estimate_confidence(chunks, category_confidence=-1.0)
    assert result == 0.0


# --- zero-chunks refusal path: never fabricate an answer -------------------

def test_draft_refuses_when_no_chunks_retrieved():
    result = draft(
        ticket_text="some ticket text",
        chunks=[],
        urgency_score=0.9,
        category_confidence=0.9,
    )
    assert result.tier == "none"
    assert result.confidence == 0.0
    assert result.source_chunk_ids == []
    assert "No relevant knowledge base information" in result.draft_text
    # Confirms this refusal is unconditional — even a high-urgency,
    # high-confidence-category ticket still gets refused with zero chunks.


def test_unavailable_message_constant_is_distinct_from_refusal_message():
    """Sanity check these are two different, deliberately distinct
    messages: one means 'nothing relevant found', the other means
    'a model call failed after retries' — conflating them would hide
    which failure mode actually happened."""
    result = draft(ticket_text="x", chunks=[], urgency_score=0.1, category_confidence=0.5)
    assert result.draft_text != UNAVAILABLE_MESSAGE
