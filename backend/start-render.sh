#!/bin/sh
# Render free-tier workaround: Render's Background Worker service type
# requires a paid plan, but nothing stops a Web Service (free forever,
# cold-starts after 15min idle) from running a second process alongside
# the one Render actually health-checks. This starts the real Celery
# worker in the background, then execs uvicorn in the foreground as the
# container's main process — same Celery/Redis architecture as the rest
# of the project, just sharing one container/service instead of two.
set -e

echo "Running migrations..."
alembic upgrade head

echo "Starting Celery worker in the background..."
celery -A app.worker worker --loglevel=info &

echo "Starting API (foreground, bound to \$PORT=${PORT:-8000})..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
