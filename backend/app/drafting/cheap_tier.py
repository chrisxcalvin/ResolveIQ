"""Cheap-tier drafting: LoRA fine-tuned Qwen2.5-0.5B-Instruct for routine tickets."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from app.core.tracing import observe
from app.drafting.prompts import build_cheap_tier_messages

ADAPTER_DIR = Path(__file__).parent.parent / "ml" / "finetune" / "artifacts" / "drafting_lora"


@dataclass(frozen=True)
class CheapTierResult:
    reply: str


@lru_cache(maxsize=1)
def _load_model():
    from unsloth import FastLanguageModel

    if not ADAPTER_DIR.exists():
        raise FileNotFoundError(
            f"No fine-tuned adapter at {ADAPTER_DIR}. Run "
            "`uv run python -m app.ml.finetune.train` first."
        )

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=str(ADAPTER_DIR),
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=False,
    )
    FastLanguageModel.for_inference(model)
    return model, tokenizer


@observe(name="cheap_tier_generation", as_type="generation")
def draft_cheap_tier(ticket_text: str, context: str) -> CheapTierResult:
    model, tokenizer = _load_model()
    messages = build_cheap_tier_messages(ticket_text, context)

    inputs = tokenizer.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
    ).to(model.device)

    outputs = model.generate(
        input_ids=inputs,
        max_new_tokens=200,
        temperature=0.3,
        do_sample=True,
        pad_token_id=tokenizer.eos_token_id,
    )
    generated = outputs[0][inputs.shape[-1] :]
    reply = tokenizer.decode(generated, skip_special_tokens=True).strip()
    return CheapTierResult(reply=reply)
