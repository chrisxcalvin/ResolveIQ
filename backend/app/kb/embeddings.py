"""Local embedding model — sentence-transformers, no external API/key needed."""

from functools import lru_cache

from app.core.tracing import observe

MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _load_model():
    # Lazy import: sentence-transformers pulls in torch (~300-500MB just to
    # import, before loading any weights). This module gets imported by the
    # API process too (tickets.py -> app.tasks, to reference process_ticket
    # for .delay()), but only the Celery worker ever actually calls
    # embed_text/embed_texts — deferring the import here keeps the API
    # process from paying torch's memory cost for a model it never uses.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL_NAME)


@observe(name="embed_texts", as_type="embedding")
def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _load_model()
    return model.encode(texts, normalize_embeddings=True).tolist()


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
