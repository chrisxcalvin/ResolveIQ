"""Category-filtered, boost-aware top-k retrieval over kb_chunks.

Usage: uv run python -m app.retrieval.retrieve "<query>" [category]
"""

import asyncio
import sys
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import SessionLocal
from app.kb.embeddings import embed_text
from app.models.kb import KbChunk, KbDocument

# Feedback loop (App Flow step 7): approving a draft as-is is a signal the
# cited chunks were good; editing it is a signal they weren't sufficient.
# Multiplicative and clamped so repeated corrections can't drive boost to
# zero/negative or run away unbounded.
APPROVE_BOOST_FACTOR = 1.05
CORRECTION_BOOST_FACTOR = 0.85
MIN_RETRIEVAL_BOOST = 0.1
MAX_RETRIEVAL_BOOST = 3.0


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: str
    document_title: str
    content: str
    similarity: float


async def retrieve(
    db: AsyncSession, query: str, category: str | None = None, top_k: int = 5
) -> list[RetrievedChunk]:
    query_embedding = embed_text(query)
    distance = KbChunk.embedding.cosine_distance(query_embedding)

    # Dividing distance by retrieval_boost ranks boosted chunks higher
    # (boost > 1 shrinks effective distance) — this is the feedback-loop
    # mechanism's read side; the write side (adjusting retrieval_boost after
    # a correction) comes later once the correction pipeline exists.
    stmt = (
        select(KbChunk, KbDocument.title, distance)
        .join(KbDocument, KbChunk.document_id == KbDocument.id)
        .order_by(distance / KbChunk.retrieval_boost)
        .limit(top_k)
    )
    if category is not None:
        stmt = stmt.where(KbDocument.category == category)

    result = await db.execute(stmt)
    rows = result.all()

    retrieved = [
        RetrievedChunk(
            chunk_id=str(chunk.id),
            document_title=title,
            content=chunk.content,
            similarity=1 - float(dist),
        )
        for chunk, title, dist in rows
    ]

    for chunk, _, _ in rows:
        chunk.times_retrieved += 1
    await db.commit()

    return retrieved


async def adjust_retrieval_boost(
    db: AsyncSession, chunk_ids: list[uuid.UUID], *, corrected: bool
) -> None:
    """Feedback-loop write side: nudges retrieval_boost after a human outcome.

    `corrected=True` means an agent edited the draft that cited these chunks
    (the retrieved content wasn't sufficient on its own); `corrected=False`
    means the agent approved it unchanged (the chunks did their job).

    Does not commit — callers run this alongside other writes (the
    resolution row, correction_signals, audit_log) in one transaction.
    """
    if not chunk_ids:
        return

    factor = CORRECTION_BOOST_FACTOR if corrected else APPROVE_BOOST_FACTOR
    chunks = (
        (await db.execute(select(KbChunk).where(KbChunk.id.in_(chunk_ids)))).scalars().all()
    )
    for chunk in chunks:
        chunk.retrieval_boost = max(
            MIN_RETRIEVAL_BOOST, min(MAX_RETRIEVAL_BOOST, chunk.retrieval_boost * factor)
        )
        if corrected:
            chunk.times_corrected_against += 1


async def _cli() -> None:
    if len(sys.argv) < 2:
        print('Usage: uv run python -m app.retrieval.retrieve "<query>" [category]')
        sys.exit(1)

    query = sys.argv[1]
    category = sys.argv[2] if len(sys.argv) > 2 else None

    async with SessionLocal() as db:
        results = await retrieve(db, query, category)

    print(f"Query: {query!r}  category={category!r}")
    for r in results:
        print(f"  [{r.similarity:.3f}] {r.document_title}: {r.content[:100]}...")


if __name__ == "__main__":
    asyncio.run(_cli())
