"""LoRA fine-tunes Qwen2.5-0.5B-Instruct into the cheap-tier drafting model.

Usage: uv run python -m app.ml.finetune.train
"""

from pathlib import Path

from datasets import Dataset

from app.drafting.prompts import build_cheap_tier_messages
from app.ml.finetune.data import generate_finetune_examples

BASE_MODEL = "unsloth/Qwen2.5-0.5B-Instruct"
ARTIFACT_DIR = Path(__file__).parent / "artifacts" / "drafting_lora"
MAX_SEQ_LENGTH = 2048


def main() -> None:
    from unsloth import FastLanguageModel
    from trl import SFTConfig, SFTTrainer

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=BASE_MODEL,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=False,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=[
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    examples = generate_finetune_examples()
    print(f"Fine-tuning dataset size: {len(examples)}")

    def to_text(example: dict) -> dict:
        messages = build_cheap_tier_messages(example["ticket_text"], example["context"]) + [
            {"role": "assistant", "content": example["reply"]}
        ]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=False)
        return {"text": text}

    def tokenize(example: dict) -> dict:
        return tokenizer(example["text"], truncation=True, max_length=MAX_SEQ_LENGTH)

    dataset = (
        Dataset.from_list(
            [{"ticket_text": e.ticket_text, "context": e.context, "reply": e.reply} for e in examples]
        )
        .map(to_text)
        .map(tokenize, remove_columns=["ticket_text", "context", "reply", "text"])
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        max_seq_length=MAX_SEQ_LENGTH,
        args=SFTConfig(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            num_train_epochs=3,
            learning_rate=2e-4,
            logging_steps=5,
            # Dataset is pre-tokenized above via plain in-process .map()
            # calls (no num_proc => no multiprocessing). skip_prepare_dataset
            # bypasses Unsloth's own tokenization pass, which ignores
            # dataset_num_proc on Windows and always spawns cpu_count()+4
            # worker processes — each reloading numpy/pandas/torch from
            # scratch, which blows out RAM on this 16GB machine. Worse, those
            # workers can't unpickle closures referencing the dynamically
            # generated unsloth_compiled_cache.UnslothSFTTrainer module, so
            # even num_proc=1 crashes.
            dataset_kwargs={"skip_prepare_dataset": True},
            optim="adamw_8bit",
            output_dir=str(ARTIFACT_DIR.parent / "checkpoints"),
            report_to="none",
            seed=42,
        ),
    )
    trainer.train()

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(ARTIFACT_DIR))
    tokenizer.save_pretrained(str(ARTIFACT_DIR))
    print(f"Saved LoRA adapter to {ARTIFACT_DIR}")


if __name__ == "__main__":
    main()
