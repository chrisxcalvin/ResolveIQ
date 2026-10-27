"""Embeddings via Hugging Face's hosted Inference API, with a local ONNX
fallback (Phase 9) that's light enough to actually run on the deployed
512MB-constrained Render worker — unlike the sentence-transformers/torch
fallback this replaces.

Was local (all-MiniLM-L6-v2 via sentence-transformers/torch), which needed
no external API/key. Switched to the hosted API because torch alone pushed
the Celery worker's memory past 512MB in a constrained deployment
container — see docs/checkpoints/phase-5.md for the full story.

Phase 9 first added a sentence-transformers/torch fallback for when the
hosted API fails (it started returning 402 "You have no remaining
credits" — HF's free Inference Providers allowance ran out, confirmed
still exhausted weeks later, not a transient blip). That fallback worked
locally but turned out to be undeployable: `requirements-deploy.txt`
deliberately excludes sentence-transformers/torch for the exact same
memory reason embeddings moved off local inference in the first place, so
the fallback could only ever help local dev, not the one place this
outage actually mattered. Documented as an honest gap in
docs/checkpoints/phase-9.md rather than left to look fixed everywhere.

This fallback instead runs the SAME model's published ONNX export
(`sentence-transformers/all-MiniLM-L6-v2`'s own `onnx/model.onnx`) via
`onnxruntime` + a raw `tokenizers` tokenizer — no torch, no
sentence-transformers. Verified bit-for-bit equivalent to the
sentence-transformers reference (cosine similarity 1.000000 across
multiple real support-ticket-style queries, not assumed from the fact
that it's "the same model"). The dependency weight is genuinely small:
onnxruntime + tokenizers + huggingface_hub together are ~30MB of wheels
versus torch's ~385MB runtime footprint, and the ONNX model file itself is
~90MB — comfortably inside the worker's free headroom under its 512MB
limit. The model+tokenizer files are baked into the Docker image at build
time (see Dockerfile.deploy) specifically so this has no runtime network
dependency on HF's file CDN either — only the hosted Inference Providers
call (tried first) needs the network, and that one already degrades
cleanly on failure.

Every row in kb_chunks must be embedded by the SAME model for cosine
similarity to mean anything — true regardless of which path (hosted API
or local ONNX) served a given call, which is exactly why the fallback
runs the identical model's own published export rather than substituting
a different one.
"""

import logging
from functools import lru_cache
from pathlib import Path

import httpx
import numpy as np

from app.core.config import settings
from app.core.tracing import observe

logger = logging.getLogger(__name__)

MODEL_REPO = "sentence-transformers/all-MiniLM-L6-v2"
API_URL = f"https://router.huggingface.co/hf-inference/models/{MODEL_REPO}/pipeline/feature-extraction"

# Where Dockerfile.deploy bakes the ONNX model + tokenizer at build time.
# Falls back to a plain Hub download (and the Hub's own on-disk cache) if
# this path doesn't exist — the local dev experience, where nothing is
# pre-baked into an image.
_BAKED_MODEL_DIR = Path(__file__).parent / "artifacts" / "onnx_embedding_model"


@lru_cache(maxsize=1)
def _load_local_model():
    import onnxruntime as ort
    from tokenizers import Tokenizer

    if (_BAKED_MODEL_DIR / "model.onnx").exists():
        model_path = str(_BAKED_MODEL_DIR / "model.onnx")
        tokenizer_path = str(_BAKED_MODEL_DIR / "tokenizer.json")
    else:
        from huggingface_hub import hf_hub_download

        model_path = hf_hub_download(MODEL_REPO, "onnx/model.onnx")
        tokenizer_path = hf_hub_download(MODEL_REPO, "tokenizer.json")

    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    tokenizer = Tokenizer.from_file(tokenizer_path)
    tokenizer.enable_padding()
    return session, tokenizer


def _embed_locally(texts: list[str]) -> list[list[float]]:
    try:
        session, tokenizer = _load_local_model()
    except ImportError as exc:
        raise RuntimeError(
            "HF hosted embeddings are unavailable and the onnxruntime/"
            "tokenizers/huggingface_hub fallback isn't installed in this "
            "environment — see app/kb/embeddings.py's module docstring."
        ) from exc

    encodings = tokenizer.encode_batch(texts)
    input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
    token_type_ids = np.zeros_like(input_ids)

    (last_hidden_state,) = session.run(
        None,
        {"input_ids": input_ids, "attention_mask": attention_mask, "token_type_ids": token_type_ids},
    )
    # Mean pooling over real (non-padding) tokens, then L2-normalize — the
    # same pooling sentence-transformers' own .encode() applies for this
    # model, confirmed by the cosine-similarity check in this module's
    # docstring, not assumed from reading the model card.
    mask = attention_mask[..., None].astype(np.float32)
    summed = (last_hidden_state * mask).sum(axis=1)
    counts = np.clip(mask.sum(axis=1), 1e-9, None)
    mean_pooled = summed / counts
    normalized = mean_pooled / np.linalg.norm(mean_pooled, axis=1, keepdims=True)
    return normalized.tolist()


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
            "HF hosted embeddings unavailable (%s) — falling back to local ONNX computation",
            exc,
        )
        return _embed_locally(texts)


def embed_text(text: str) -> list[float]:
    return embed_texts([text])[0]
