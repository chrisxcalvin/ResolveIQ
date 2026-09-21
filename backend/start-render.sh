#!/bin/sh
# API service only. Runs alongside a SEPARATE worker service
# (start-worker.sh) rather than sharing this container — see
# docs/checkpoints/phase-5.md: the worker alone needed ~662MB at runtime
# before the Gemini-embeddings + trimmed-spaCy fixes, which was already
# over Render's 512MB free-tier limit on its own, so combining it with
# the API in one container was never going to fit safely either way.
set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting API (foreground, bound to \$PORT=${PORT:-8000})..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
