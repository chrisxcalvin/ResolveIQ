"""Embeddings via the Gemini API — not local sentence-transformers.

Was local (all-MiniLM-L6-v2 via sentence-transformers/torch), which needed
no external API/key. Switched because torch alone pushed the Celery
worker's memory past 512MB in a constrained deployment container — see
docs/checkpoints/phase-5.md for the full story, including the two other
fixes (lazy-importing torch/spacy in the API process, trimming spaCy's
pipeline) that weren't sufficient on their own.

Truncated to 384 dimensions (EMBEDDING_DIM in app/models/kb.py) to match
the existing pgvector column exactly, avoiding a schema migration. Gemini's
embedding models are trained with Matryoshka representation learning
specifically so truncation degrades gracefully rather than corrupting the
embedding.

Every row in kb_chunks must be embedded by the SAME model for cosine
similarity to mean anything — this is why the switch had to be a full
re-embed of the corpus (`uv run python -m app.kb.embed`), not a
per-environment toggle. Local dev and the deployed app share one Neon
database; a local-dev-only fallback here would have silently corrupted
retrieval by mixing two incompatible embedding spaces in one column.
"""

import httpx

from app.core.config import settings
from app.core.tracing import observe
from app.models.kb import EMBEDDING_DIM

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:batchEmbedContents"


@observe(name="embed_texts", as_type="embedding")
def embed_texts(texts: list[str]) -> list[list[float]]:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    url = API_URL.format(model=settings.gemini_embedding_model)
    model_path = f"models/{settings.gemini_embedding_model}"
    payload = {
        "requests": [
            {
                "model": model_path,
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": EMBEDDING_DIM,
            }
            for text in texts
        ]
    }
    response = httpx.post(
        url,
        json=payload,
        headers={"x-goog-api-key": settings.gemini_api_key},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return [item["values"] for item in data["embeddings"]]


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
