"""Chunks and embeds the KB articles into pgvector.

Usage: uv run python -m app.kb.embed
"""

import asyncio
import re
from pathlib import Path

from sqlalchemy import delete, select

from app.db.base import SessionLocal
from app.kb.embeddings import embed_texts
from app.models.kb import KbChunk, KbDocument

ARTICLES_DIR = Path(__file__).parent / "articles"


def _parse_article(path: Path) -> tuple[str, str, str]:
    text = path.read_text(encoding="utf-8")
    _, frontmatter, body = text.split("---", 2)
    meta = {}
    for line in frontmatter.strip().splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip()
    return meta["title"], meta["category"], body.strip()


def _chunk(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


async def embed_articles() -> None:
    async with SessionLocal() as db:
        total_docs = 0
        total_chunks = 0

        for path in sorted(ARTICLES_DIR.glob("*.md")):
            title, category, body = _parse_article(path)
            chunks = _chunk(body)

            result = await db.execute(select(KbDocument).where(KbDocument.title == title))
            document = result.scalar_one_or_none()
            if document is None:
                document = KbDocument(title=title, category=category, source_type="help_doc")
                db.add(document)
                await db.flush()
            else:
                # Re-running should replace old chunks/metadata, not duplicate
                # them or leave stale values (e.g. a previously mis-encoded
                # title) stuck from an earlier run.
                document.title = title
                document.category = category
                await db.execute(delete(KbChunk).where(KbChunk.document_id == document.id))

            embeddings = embed_texts(chunks)
            for content, embedding in zip(chunks, embeddings):
                db.add(KbChunk(document_id=document.id, content=content, embedding=embedding))

            total_docs += 1
            total_chunks += len(chunks)

        await db.commit()
        print(f"Embedded {total_docs} documents, {total_chunks} chunks.")


if __name__ == "__main__":
    asyncio.run(embed_articles())
