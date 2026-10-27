"""Embeddings via Hugging Face's hosted Inference API, with a local
fallback (Phase 9) that's only actually usable in environments that have
`sentence-transformers`/torch installed — NOT the deployed Render worker.

Was local (all-MiniLM-L6-v2 via sentence-transformers/torch), which needed
no external API/key. Switched to the hosted API because torch alone pushed
the Celery worker's memory past 512MB in a constrained deployment
container — see docs/checkpoints/phase-5.md for the full story. That
constraint is still real: `requirements-deploy.txt` deliberately excludes
`sentence-transformers` for exactly this reason, so the fallback below
CANNOT help the deployed worker — see the honest correction in
docs/checkpoints/phase-9.md for how this was initially overstated.

Phase 9 added the fallback after the hosted API started returning 402
"You have no remaining credits" — HF's free Inference Providers allowance
ran out, and confirmed (not assumed) to still be out weeks later, so this
isn't a transient blip. In an environment where `sentence-transformers` IS
installed (local dev, or any future deployment with the memory budget for
it), the fallback computes the exact same model locally so the embedding
space never diverges from what's already in `kb_chunks`. In the deployed
Render worker, the import simply isn't available, so `_embed_locally`
raises a clear, actionable error instead of degrading — a loud, correctly-
labeled failure beats a confusing `ModuleNotFoundError` bubbling up from
inside an `except` block, even though neither one actually fixes
retrieval on that specific deployment. HF's classic
api-inference.huggingface.co endpoint is gone; router.huggingface.co is
the current one.

Every row in kb_chunks must be embedded by the SAME model for cosine
similarity to mean anything — true whether a given call was served by the
hosted API or the local fallback, which is exactly why the fallback loads
the identical model by name rather than substituting something else.
"""

import logging
from functools import lru_cache

import httpx

from app.core.config import settings
from app.core.tracing import observe

logger = logging.getLogger(__name__)

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL}/pipeline/feature-extraction"


@lru_cache(maxsize=1)
def _load_local_model():
    # Lazy import + lazy load: this cost (pulling in sentence-transformers/
    # torch and loading weights) is only ever paid on a process that
    # actually hits the hosted-API fallback AND has the package installed
    # (local dev — see module docstring for why the deployed worker can't).
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL)


def _embed_locally(texts: list[str]) -> list[list[float]]:
    try:
        model = _load_local_model()
    except ImportError as exc:
        raise RuntimeError(
            "HF hosted embeddings are unavailable and sentence-transformers "
            "isn't installed in this environment (expected on the deployed "
            "Render worker — see app/kb/embeddings.py's module docstring), "
            "so there is no fallback path here."
        ) from exc
    return model.encode(texts, normalize_embeddings=False).tolist()


@observe(name="embed_texts", as_type="embedding")
def embed_texts(texts: list[str]) -> list[list[float]]:
    if not settings.hf_api_key:
        raise RuntimeError("HF_API_KEY is not set")

    try:
        response = httpx.post(
            API_URL,
            json={"inputs": texts},
            headers={"Authorization": f"Bearer {settings.hf_api_key}"},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning(
            "HF hosted embeddings unavailable (%s) — attempting local fallback",
            exc,
        )
        return _embed_locally(texts)


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
