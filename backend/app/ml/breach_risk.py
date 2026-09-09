"""Inference wrapper around the trained SLA breach-risk classifier (Feature 3)."""

from functools import lru_cache

import joblib
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.train_breach_risk import ARTIFACT_PATH
from app.models.ticket import Ticket

# Tickets in these statuses are still sitting in the queue awaiting action —
# this is the "queue depth" input to the synthetic breach-risk rule.
OPEN_STATUSES = ("new", "classified", "drafted")


async def get_queue_depth(db: AsyncSession, category: str) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Ticket)
        .where(Ticket.category == category, Ticket.status.in_(OPEN_STATUSES))
    )
    return int(result.scalar_one())


@lru_cache(maxsize=1)
def _load_artifact() -> dict:
    if not ARTIFACT_PATH.exists():
        raise FileNotFoundError(
            f"No trained breach-risk artifact at {ARTIFACT_PATH}. Run "
            "`uv run python -m app.ml.train_breach_risk` first."
        )
    return joblib.load(ARTIFACT_PATH)


def score_breach_risk(
    age_minutes: float, category: str, urgency_score: float, queue_depth: int
) -> float:
    pipeline = _load_artifact()["pipeline"]
    row = pd.DataFrame(
        [
            {
                "age_minutes": age_minutes,
                "category": category,
                "urgency_score": urgency_score,
                "queue_depth": queue_depth,
            }
        ]
    )
    # Probability of the positive ("breach risk") class.
    return float(pipeline.predict_proba(row)[0][1])
