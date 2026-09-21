"""Embeddings via Hugging Face's hosted Inference API — not local
sentence-transformers/torch.

Was local (all-MiniLM-L6-v2 via sentence-transformers/torch), which needed
no external API/key. Switched because torch alone pushed the Celery
worker's memory past 512MB in a constrained deployment container — see
docs/checkpoints/phase-5.md for the full story.

This calls the SAME model (sentence-transformers/all-MiniLM-L6-v2) hosted
by Hugging Face, so the embedding space is identical to what local
inference always produced — no dimension truncation or re-tuning needed,
unlike the Gemini API this briefly used instead (which hit a real
"prepayment credits depleted" paywall despite documented claims of a free
tier — verified directly, not assumed). HF's classic api-inference.huggingface.co
endpoint is gone; router.huggingface.co is the current one.

Every row in kb_chunks must be embedded by the SAME model for cosine
similarity to mean anything. Since local dev and the deployed app share
one Neon database, this had to be a full swap (re-embed via
`uv run python -m app.kb.embed`), not a per-environment toggle — a
local-only fallback would have silently mixed incompatible embedding
spaces in one column.
"""

import httpx

from app.core.config import settings
from app.core.tracing import observe

MODEL = "sentence-transformers/all-MiniLM-L6-v2"
API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL}/pipeline/feature-extraction"


@observe(name="embed_texts", as_type="embedding")
def embed_texts(texts: list[str]) -> list[list[float]]:
    if not settings.hf_api_key:
        raise RuntimeError("HF_API_KEY is not set")

    response = httpx.post(
        API_URL,
        json={"inputs": texts},
        headers={"Authorization": f"Bearer {settings.hf_api_key}"},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
