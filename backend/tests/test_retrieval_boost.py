"""Phase 2: retrieval-boost math (app/retrieval/retrieve.py::adjust_retrieval_boost).

Needs a real DB — the function reads/writes an actual KbChunk row — so
these use the transactional db_session fixture from conftest.py rather
than being pure-function tests.
"""

import pytest

from app.models.kb import KbChunk, KbDocument
from app.retrieval.retrieve import (
    APPROVE_BOOST_FACTOR,
    CORRECTION_BOOST_FACTOR,
    MAX_RETRIEVAL_BOOST,
    MIN_RETRIEVAL_BOOST,
    adjust_retrieval_boost,
)


async def _make_chunk(db_session, boost: float) -> KbChunk:
    doc = KbDocument(title="test doc", category="general_query", source_type="help_doc")
    db_session.add(doc)
    await db_session.flush()

    chunk = KbChunk(document_id=doc.id, content="test content", retrieval_boost=boost)
    db_session.add(chunk)
    await db_session.flush()
    return chunk


@pytest.mark.asyncio
async def test_approve_multiplies_boost_by_approve_factor(db_session):
    chunk = await _make_chunk(db_session, boost=1.0)
    await adjust_retrieval_boost(db_session, [chunk.id], corrected=False)
    assert chunk.retrieval_boost == pytest.approx(1.0 * APPROVE_BOOST_FACTOR)


@pytest.mark.asyncio
async def test_edit_multiplies_boost_by_correction_factor(db_session):
    chunk = await _make_chunk(db_session, boost=1.0)
    await adjust_retrieval_boost(db_session, [chunk.id], corrected=True)
    assert chunk.retrieval_boost == pytest.approx(1.0 * CORRECTION_BOOST_FACTOR)


@pytest.mark.asyncio
async def test_edit_increments_times_corrected_against(db_session):
    chunk = await _make_chunk(db_session, boost=1.0)
    assert chunk.times_corrected_against == 0
    await adjust_retrieval_boost(db_session, [chunk.id], corrected=True)
    assert chunk.times_corrected_against == 1


@pytest.mark.asyncio
async def test_approve_does_not_increment_times_corrected_against(db_session):
    chunk = await _make_chunk(db_session, boost=1.0)
    await adjust_retrieval_boost(db_session, [chunk.id], corrected=False)
    assert chunk.times_corrected_against == 0


@pytest.mark.asyncio
async def test_boost_clamps_at_max_and_never_exceeds_it(db_session):
    """Starting near the ceiling, repeated approvals must not push the
    boost past MAX_RETRIEVAL_BOOST."""
    chunk = await _make_chunk(db_session, boost=MAX_RETRIEVAL_BOOST - 0.05)
    for _ in range(5):
        await adjust_retrieval_boost(db_session, [chunk.id], corrected=False)
    assert chunk.retrieval_boost == pytest.approx(MAX_RETRIEVAL_BOOST)
    assert chunk.retrieval_boost <= MAX_RETRIEVAL_BOOST


@pytest.mark.asyncio
async def test_boost_clamps_at_min_and_never_drops_below_it(db_session):
    """Starting near the floor, repeated corrections must not push the
    boost below MIN_RETRIEVAL_BOOST — otherwise a chunk could be pushed
    to zero/negative and become permanently unretrievable."""
    chunk = await _make_chunk(db_session, boost=MIN_RETRIEVAL_BOOST + 0.05)
    for _ in range(5):
        await adjust_retrieval_boost(db_session, [chunk.id], corrected=True)
    assert chunk.retrieval_boost == pytest.approx(MIN_RETRIEVAL_BOOST)
    assert chunk.retrieval_boost >= MIN_RETRIEVAL_BOOST


@pytest.mark.asyncio
async def test_boost_exactly_at_max_stays_clamped_on_further_approval(db_session):
    chunk = await _make_chunk(db_session, boost=MAX_RETRIEVAL_BOOST)
    await adjust_retrieval_boost(db_session, [chunk.id], corrected=False)
    assert chunk.retrieval_boost == MAX_RETRIEVAL_BOOST


@pytest.mark.asyncio
async def test_boost_exactly_at_min_stays_clamped_on_further_correction(db_session):
    chunk = await _make_chunk(db_session, boost=MIN_RETRIEVAL_BOOST)
    await adjust_retrieval_boost(db_session, [chunk.id], corrected=True)
    assert chunk.retrieval_boost == MIN_RETRIEVAL_BOOST


@pytest.mark.asyncio
async def test_empty_chunk_id_list_is_a_safe_no_op(db_session):
    """resolve_ticket calls this even when a draft cited zero chunks
    (draft.source_chunk_ids or []) — must not error."""
    await adjust_retrieval_boost(db_session, [], corrected=True)
    await adjust_retrieval_boost(db_session, [], corrected=False)


@pytest.mark.asyncio
async def test_multiple_chunks_all_adjusted_together(db_session):
    chunk_a = await _make_chunk(db_session, boost=1.0)
    chunk_b = await _make_chunk(db_session, boost=2.0)
    await adjust_retrieval_boost(db_session, [chunk_a.id, chunk_b.id], corrected=False)
    assert chunk_a.retrieval_boost == pytest.approx(1.0 * APPROVE_BOOST_FACTOR)
    assert chunk_b.retrieval_boost == pytest.approx(2.0 * APPROVE_BOOST_FACTOR)
