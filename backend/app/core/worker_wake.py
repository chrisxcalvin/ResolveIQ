"""Best-effort wake-up ping for the Celery worker on Render's free tier.

Render spins a free service down after ~15 minutes without inbound HTTP
traffic. A queued Celery task is not inbound HTTP traffic - it just sits in
Redis - so nothing wakes a sleeping worker, and a ticket submitted while it
sleeps stays "new" until something else happens to hit the worker's URL.

The first attempt at fixing this was a GitHub Actions cron pinging the
worker every 10 minutes (.github/workflows/keep-worker-awake.yml). That
turned out to be unreliable: GitHub treats scheduled workflows on free
repos as best-effort, and a `*/10` schedule was observed actually firing
every 3-6 hours, leaving the worker asleep almost all the time. So the
wake-up is tied to the event that actually needs the worker instead - a
ticket being submitted - and no longer depends on any external scheduler.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# Render can take 30-50s to spin a service back up and holds the request
# until the instance answers. This runs as a FastAPI BackgroundTask, i.e.
# after the response has already been sent, so a long timeout costs the
# person who submitted the ticket nothing.
WAKE_TIMEOUT_SECONDS = 70.0


async def wake_worker() -> None:
    url = settings.worker_wake_url
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=WAKE_TIMEOUT_SECONDS) as client:
            await client.get(url)
    except Exception:
        # Best-effort only: the task is already safely queued in Redis, so
        # a failed ping just means the worker wakes a bit later.
        logger.warning("Worker wake-up ping failed", exc_info=True)
