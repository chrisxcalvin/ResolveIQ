"""Category-filtered, boost-aware top-k retrieval over kb_chunks.

Usage: uv run python -m app.retrieval.retrieve "<query>" [category]
"""

import asyncio
import sys
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import SessionLocal
from app.kb.embeddings import embed_text
from app.models.kb import KbChunk, KbDocument


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
