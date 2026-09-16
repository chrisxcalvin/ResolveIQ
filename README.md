# ResolveIQ

An AI-assisted support-ticket triage tool for a fintech company. A ticket
comes in, gets classified and PII-redacted, relevant knowledge-base content
is retrieved, a grounded draft reply is generated with cited sources and a
confidence score, and a human agent approves, edits, or escalates it. Edits
feed back into retrieval ranking, so a correction on one ticket measurably
improves the draft on the next similar one — that feedback loop is the
project's core mechanic (see [04_App_Flow.md](04_App_Flow.md)).

Full spec docs: [01_PRD.md](01_PRD.md) · [02_TRD.md](02_TRD.md) ·
[03_UI_UX_Design.md](03_UI_UX_Design.md) · [04_App_Flow.md](04_App_Flow.md) ·
[05_Backend_Schema.md](05_Backend_Schema.md) ·
[06_Implementation_Plan.md](06_Implementation_Plan.md) · [DATA.md](DATA.md)
(what's real training data vs. synthetic vs. authored, and why) ·
[BUILD_SPEC.md](BUILD_SPEC.md) (the phased post-launch hardening plan —
bugs, tests, real data, deployment, UI, customer portal, benchmarking) ·
[docs/checkpoints/](docs/checkpoints/) (an interview-prep writeup per
phase: what was built, why, failure modes, and the honest answer to the
hardest follow-up question)

## Architecture

```mermaid
flowchart LR
    subgraph Pipeline["LangGraph pipeline (app/pipeline/graph.py), one run per ticket, async via Celery"]
        direction LR
        A[redact] --> B[classify]
        B --> C[breach_risk]
        C --> D[retrieve]
        D --> E[customer_context]
        E --> F[draft]
        F --> G[decide]
    end

    Ticket[POST /tickets] -->|status=new, enqueue| Pipeline
    Pipeline --> DB[(Postgres + pgvector)]
    F -->|urgency < threshold| Cheap[Cheap tier: LoRA-fine-tuned Qwen2.5-0.5B]
    F -->|urgency >= threshold| Strong[Strong tier: Groq-hosted gpt-oss-120b]
    Agent[Human agent: approve / edit / escalate] --> DB
    Agent -->|edit| Correction[correction_signals] --> Boost[retrieval_boost on kb_chunks] --> D
```

Four pipeline "agents" in the TRD's sense (distinct, inspectable steps — not
autonomous free-acting agents): a trained classifier (category + urgency,
not an LLM guess), a pgvector retrieval agent (category-filtered,
correction-boosted), a drafting agent (cost-routed between a locally
fine-tuned small model and a stronger hosted one), and a decision agent
(confidence + urgency + category → review routing, never auto-send).

## Features

1. **Drafting + feedback loop** (core, built deep) — classify → retrieve →
   draft → decide, human review, corrections re-rank retrieval.
2. **Customer history context** — a summary of a customer's prior tickets is
   injected into the (strong-tier) drafting prompt.
3. **SLA breach-risk prioritization** — a small classifier trained on a
   synthetic age/category/urgency/queue-depth rule reorders the queue.
4. **Agent coaching insights** — edit-distance, resolution time, and
   escalation rate aggregated per agent; pure reporting, no new backend logic.

## Production LLM techniques

| Technique | Where it lives |
|---|---|
| Structured output | `app/ml/classifier.py` — trained classifier, not an LLM guess |
| Grounding + citations | `app/drafting/draft.py` — every draft cites the chunks it used |
| Prompt versioning | `app/drafting/prompts.py` — prompts as versioned functions, not inline strings |
| Model routing | `app/drafting/draft.py` — LoRA-fine-tuned small model for routine tickets, Groq-hosted model for harder/urgent ones |
| Retry + timeout + fallback | `app/drafting/draft.py` (`tenacity` retry + "needs manual response" fallback on exhaustion) |
| Guardrails (PII redaction) | `app/redaction/pii.py` — runs before any LLM call or log write |
| Observability/tracing | `app/core/tracing.py` — Langfuse `@observe` on every pipeline node + LLM/embedding call |
| Automated evaluation | `app/eval/ragas_eval.py` — RAGAS non-LLM context precision/recall on an 18-example held-out set |
| Feedback loop | `app/retrieval/retrieve.py` (`adjust_retrieval_boost`) — the project's one differentiating mechanic |

## Tech stack

FastAPI (async) · PostgreSQL + pgvector · LangGraph · Celery + Redis ·
Next.js · JWT auth (access + rotated refresh) · Langfuse · RAGAS · Docker
Compose. Rationale for each choice is in
[02_TRD.md](02_TRD.md#1-tech-stack-and-why).

## Quick start

Everything currently runs as **native processes — no Docker.** Docker
Desktop was unstable on this project's dev machine, so Postgres and Redis
run inside a plain WSL2 Ubuntu distro (not Docker Desktop's own WSL2
containers), and the API/worker/frontend all run directly on the host.
`docker-compose.yml` and the `api`/`frontend` Dockerfiles still exist and
are kept up to date if you'd rather containerize (see the note at the
bottom of this section), but the setup below is what's actually verified
working day to day.

### Postgres + Redis (WSL2 Ubuntu, one-time setup)

```powershell
wsl --install -d Ubuntu --no-launch
wsl -d Ubuntu -u root -- bash -c "useradd -m -s /bin/bash resolveiq && echo 'resolveiq:resolveiq' | chpasswd && usermod -aG sudo resolveiq && echo 'resolveiq ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/resolveiq"
wsl -d Ubuntu -u root -- bash -c "printf '[user]\ndefault=resolveiq\n' > /etc/wsl.conf"
wsl --terminate Ubuntu
```

Then, inside `wsl -d Ubuntu`:

```bash
sudo apt-get update -qq
sudo apt-get install -y curl ca-certificates redis-server

# PostgreSQL's own apt repo, for pgvector packages matching PG16
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -s https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" | sudo tee /etc/apt/sources.list.d/pgdg.list
sudo apt-get update -qq
sudo apt-get install -y postgresql-16 postgresql-16-pgvector

sudo service postgresql start
sudo service redis-server start

sudo -u postgres psql -c "CREATE ROLE resolveiq LOGIN PASSWORD 'resolveiq_dev_password';"
sudo -u postgres psql -c "CREATE DATABASE resolveiq OWNER resolveiq;"
```

Every time you restart Windows, both services need restarting (they don't
survive a reboot on their own):

```powershell
wsl -d Ubuntu -u root -- bash -c "service postgresql start && service redis-server start"
```

`.env`'s `DATABASE_URL`/`REDIS_URL` already point at `localhost` — WSL2
forwards `localhost` to the Windows host by default, so no port mapping is
needed.

### Backend + frontend

```bash
cp .env.example .env   # fill in GROQ_API_KEY at minimum

cd backend
uv sync
uv run alembic upgrade head
uv run python -m app.scripts.seed_admin you@example.com yourpassword
uv run uvicorn app.main:app --reload          # terminal 1
uv run celery -A app.worker worker --loglevel=info --pool=solo   # terminal 2 (Windows needs --pool=solo)

cd frontend
npm install
npm run dev                                    # terminal 3
```

**GPU note**: the cheap-tier drafting model (a LoRA-fine-tuned Qwen2.5-0.5B)
needs `torch` to see a local GPU. No GPU available? Set
`CHEAP_TIER_URGENCY_THRESHOLD=0` in `.env` — every ticket then routes to the
Groq-hosted strong tier instead, and the worker never needs to load torch
at all.

**Containerizing instead**: `docker compose up -d postgres redis` and
`docker compose up --build frontend` are still valid if you'd rather not
set up WSL2. The `api`/`worker` Dockerfiles bundle torch + CUDA + Unsloth
(a 10-20GB image) — `docker compose build api` builds just that image so
you can gauge the size before committing to `up`; if you do run it that
way, the containers need a GPU visible via the [NVIDIA Container
Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).

## Seeding & training

Run once against a fresh database, from `backend/`:

```bash
uv run python -m app.kb.embed                  # chunk + embed the KB articles
uv run python -m app.ml.cfpb_data               # fetch real CFPB complaint narratives (~10k rows, ~2min)
uv run python -m app.ml.train_classifier        # category (real CFPB data) / urgency (synthetic) classifier
uv run python -m app.ml.train_breach_risk       # SLA breach-risk classifier (synthetic — see DATA.md)
uv run python -m app.ml.finetune.train          # LoRA fine-tune the cheap-tier model (needs GPU)
uv run python -m app.scripts.seed_demo          # pre-seeded demo tickets — see DEMO.md
```

Category classifier held-out accuracy: **0.773** (real data, see
[DATA.md](DATA.md) for the near-duplicate leakage check and what the
number does/doesn't mean). Run `uv run python -m app.ml.cfpb_data --stats`
to see the cached dataset's per-category breakdown.

## Testing

```bash
cd backend
uv run pytest
```

44 tests, ~3s. Covers PII redaction patterns, the decision agent's
routing thresholds, the confidence formula and zero-chunks refusal path,
the retrieval-boost math including both clamp boundaries, and the
double-resolve guard at the HTTP layer.

DB-backed tests use a disposable `resolveiq_test` database on the same
Postgres instance (created once — see `tests/conftest.py`), with each test
wrapped in a transaction that's rolled back afterward, so they never touch
the dev database. Create it with:

```bash
wsl -d Ubuntu -u root -- bash -c "sudo -u postgres psql -c \"CREATE DATABASE resolveiq_test OWNER resolveiq;\" && sudo -u postgres psql -d resolveiq_test -c \"CREATE EXTENSION IF NOT EXISTS vector;\""
```

### Concurrency check

Run separately, against the **live** stack (needs API + worker + Postgres
+ Redis actually running), since it can't be hermetic:

```bash
uv run python -m tests.concurrency_check 10
```

Fires N simultaneous ticket submissions and confirms none are dropped or
stuck, then fires N simultaneous resolves at a single ticket and confirms
exactly one wins and the rest get a clean 409 — the real test of the
`SELECT ... FOR UPDATE` guard on `resolve_ticket`.

**Not yet tested**, stated plainly: the pgvector similarity search itself,
classifier behaviour on given input, the LangGraph pipeline as a wired
graph, model-call retry/fallback, auth flows, rate limiting, admin
endpoints, and the entire frontend. See `docs/checkpoints/phase-2.md`.

## Eval & observability

```bash
uv run python -m app.eval.ragas_eval
```

Runs retrieval over an 18-example hand-labeled set spanning all 5 ticket
categories and reports RAGAS non-LLM context precision/recall (string
similarity against the correct KB document, no LLM judge — deterministic
and doesn't burn API quota). Latest run: **mean precision 0.79, mean recall
0.69**.

Langfuse tracing is opt-in: set `LANGFUSE_PUBLIC_KEY`/`LANGFUSE_SECRET_KEY`
in `.env` and every pipeline node plus each LLM/embedding call appears as a
trace at your configured `LANGFUSE_HOST`. Unset, it's a no-op — no code
changes needed either way.

## Demo

See [DEMO.md](DEMO.md) for the rehearsed walkthrough: pre-seeded tickets at
different urgency/breach-risk levels, one live-typed ticket, and the
correction-improves-next-draft sequence.

## Project structure

```
backend/app/
  api/routes/       FastAPI routers (auth, tickets, admin, health)
  core/              config, security, rate limiting, tracing
  db/                SQLAlchemy session/engine
  decision/          decision/escalation agent
  drafting/          drafting agent (cheap + strong tier, prompts, customer context)
  eval/              RAGAS retrieval-quality eval
  kb/                knowledge-base embedding
  ml/                trained classifiers (category/urgency, breach-risk) + LoRA fine-tune
  models/            SQLAlchemy models
  pipeline/          LangGraph state machine wiring the agents together
  redaction/         PII redaction
  retrieval/         pgvector retrieval agent + feedback-loop boost adjustment
  schemas/           Pydantic request/response models
  scripts/           admin seeding, demo seeding
  tasks.py, worker.py  Celery task + app
frontend/src/app/    Next.js pages (login, queue, ticket detail, admin views)
alembic/             DB migrations
```
