"""Celery app.

Run with: uv run celery -A app.worker worker --loglevel=info --pool=solo
(--pool=solo is required on Windows; prefork isn't supported.)
"""

from celery import Celery

from app.core.config import settings

celery_app = Celery("resolveiq", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_default_queue = "resolveiq"

# Import so the task gets registered on the app above.
import app.tasks  # noqa: E402,F401
