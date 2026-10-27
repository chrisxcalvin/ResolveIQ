"""Embeddings via Hugging Face's hosted Inference API, with a local
fallback (Phase 9) — not local-only sentence-transformers/torch.

Was local (all-MiniLM-L6-v2 via sentence-transformers/torch), which needed
no external API/key. Switched to the hosted API because torch alone pushed
the Celery worker's memory past 512MB in a constrained deployment
container — see docs/checkpoints/phase-5.md for the full story.

Phase 9 added the fallback below after the hosted API started returning
402 "You have no remaining credits" — HF's free Inference Providers
allowance is a monthly quota, not a permanent free tier, and running out of
it silently broke retrieval for every single ticket (embed_text() feeds
every real-time query through this same function). A fallback that
degrades to local computation on ANY hosted-API failure (quota, outage,
this machine's own documented intermittent network blips) keeps the
pipeline from going fully down over an external billing state it doesn't
control, at the cost of paying the local model's load/compute cost on
whichever process hits the fallback first.

This calls the SAME model (sentence-transformers/all-MiniLM-L6-v2) either
way, so the embedding space is identical regardless of which path served a
given call — no dimension truncation or re-tuning needed, unlike the
Gemini API this briefly used instead (which hit a real "prepayment credits
depleted" paywall despite documented claims of a free tier — verified
directly, not assumed). HF's classic api-inference.huggingface.co endpoint
is gone; router.huggingface.co is the current one.

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
    # torch and loading weights) is only ever paid on the process that
    # actually hits the hosted-API fallback, not on every startup.
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODEL)


def _embed_locally(texts: list[str]) -> list[list[float]]:
    return _load_local_model().encode(texts, normalize_embeddings=False).tolist()


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
            "HF hosted embeddings unavailable (%s) — falling back to local computation",
            exc,
        )
        return _embed_locally(texts)


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
