"""Strong-tier drafting: Groq-hosted llama-3.3-70b-versatile.

Used for harder/high-urgency tickets (see app/drafting/draft.py for the
routing decision). Unlike the cheap tier, this model reliably follows
structured JSON output instructions, so it self-reports which specific
context chunks it relied on.
"""

import json
from dataclasses import dataclass

from groq import Groq

from app.core.config import settings
from app.core.tracing import observe
from app.drafting.prompts import build_strong_tier_messages
from app.retrieval.retrieve import RetrievedChunk

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        _client = Groq(api_key=settings.groq_api_key)
    return _client


@dataclass(frozen=True)
class StrongTierResult:
    reply: str
    source_chunk_ids: list[str]


@observe(name="strong_tier_generation", as_type="generation")
def draft_strong_tier(
    ticket_text: str, chunks: list[RetrievedChunk], customer_history: str = ""
) -> StrongTierResult:
    numbered_context = "\n\n".join(
        f"[{c.chunk_id}] ({c.document_title}): {c.content}" for c in chunks
    )
    messages = build_strong_tier_messages(ticket_text, numbered_context, customer_history)

    response = _get_client().chat.completions.create(
        model=settings.groq_model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0.3,
    )
    payload = json.loads(response.choices[0].message.content)
    return StrongTierResult(
        reply=payload["reply"],
        source_chunk_ids=payload.get("source_chunk_ids", []),
    )
