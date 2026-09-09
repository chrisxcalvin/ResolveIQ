# Shared image for both the api and worker services (docker-compose.yml
# overrides `command:` per service — same deps, same code, different entrypoint).
#
# GPU note: the cheap-tier drafting model (Unsloth LoRA on Qwen2.5-0.5B) runs
# on the GPU visible to the container via the NVIDIA Container Toolkit /
# Docker's `nvidia` runtime (see docker-compose.yml's `deploy.resources`).
# The CUDA runtime pieces PyTorch needs ship inside the cu126 wheel itself —
# only the host's NVIDIA driver needs to be exposed, not a full CUDA image.
# If GPU passthrough isn't set up on the host, set
# CHEAP_TIER_URGENCY_THRESHOLD=0 so every ticket routes to the Groq-hosted
# strong tier instead — no local GPU inference required.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

# Dependency layer cached separately from app code.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
COPY app ./app

# Trained artifacts (classifier, breach-risk model, fine-tuned LoRA adapter)
# are baked into the image rather than mounted — this project has no
# retraining pipeline, so the artifact is effectively part of the release.
# If they're missing at build time, cheap-tier drafting/classification will
# raise FileNotFoundError at first use (see the modules' own error messages
# for the `uv run python -m app.ml....` command that (re)generates them).

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
