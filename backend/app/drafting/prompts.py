"""Versioned prompt-building functions for the drafting agent.

Treat prompts as code, not inline strings (TRD section 3, "Prompt
templating/versioning"). The cheap-tier prompt here is used both to build
the LoRA fine-tuning dataset (app/ml/finetune/train.py) and at inference
time (app/drafting/cheap_tier.py) — they must stay byte-identical, which is
why both import from here rather than duplicating the template.
"""

CHEAP_TIER_SYSTEM_PROMPT_V1 = (
    "You are a support agent assistant for a fintech company. Using ONLY the "
    "provided context, write a grounded, concise reply (2-4 sentences) to the "
    "customer's ticket. Never invent information not present in the context. "
    "End your reply with a citation in the form '(Source: <article title>)'."
)

STRONG_TIER_SYSTEM_PROMPT_V1 = (
    "You are a support agent assistant for a fintech company. You will be "
    "given a customer ticket and several numbered context chunks retrieved "
    "from the knowledge base. Using ONLY the provided context, write a "
    "grounded, concise reply (2-5 sentences). Never invent information not "
    "present in the context — if the context doesn't cover the question, say "
    "so plainly instead of guessing. Respond with a JSON object matching "
    '{"reply": string, "source_chunk_ids": string[]} where source_chunk_ids '
    "lists the ids of the context chunks you actually relied on."
)

# V2 adds an optional customer-history section (Feature 2) to the same
# contract as V1 — same required JSON shape, so callers don't need to branch.
STRONG_TIER_SYSTEM_PROMPT_V2 = (
    STRONG_TIER_SYSTEM_PROMPT_V1
    + " You may also be given a short summary of the customer's prior tickets "
    "— use it only to tailor tone (e.g. acknowledge a repeat issue), never as "
    "grounds for facts that aren't in the context chunks."
)


def build_cheap_tier_user_message(ticket_text: str, context: str) -> str:
    return f"Customer ticket:\n{ticket_text}\n\nContext:\n{context}"


def build_cheap_tier_messages(ticket_text: str, context: str) -> list[dict]:
    # Byte-identical to the template used to build the LoRA fine-tuning
    # dataset (app/ml/finetune/train.py) — do not add customer-history or
    # any other field here without retraining; drifting from the trained
    # shape degrades the fine-tuned model's output.
    return [
        {"role": "system", "content": CHEAP_TIER_SYSTEM_PROMPT_V1},
        {"role": "user", "content": build_cheap_tier_user_message(ticket_text, context)},
    ]


def build_strong_tier_messages(
    ticket_text: str, numbered_context: str, customer_history: str = ""
) -> list[dict]:
    user_content = f"Customer ticket:\n{ticket_text}\n\nContext chunks:\n{numbered_context}"
    if customer_history:
        user_content += f"\n\nCustomer history:\n{customer_history}"

    return [
        {"role": "system", "content": STRONG_TIER_SYSTEM_PROMPT_V2},
        {"role": "user", "content": user_content},
    ]
