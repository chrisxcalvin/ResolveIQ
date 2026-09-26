"""Celery task: runs a ticket through the full AI pipeline."""

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.base import SessionLocal
from app.models.audit_log import AuditLog
from app.models.ticket import Ticket
from app.models.ticket_draft import TicketDraft
from app.models.ticket_resolution import TicketResolution
from app.models.user import User
from app.pipeline.graph import run_pipeline
from app.worker import celery_app

logger = logging.getLogger(__name__)

# Sentinel actor for AUTO_RESOLVE_THRESHOLD (Phase 7, off by default) — the
# `TicketResolution.agent_id` FK is NOT NULL, so an AI-only resolution still
# needs a real `User` row to point at. Seeded by
# app/scripts/seed_portal_demo.py. Never logged in as (no real login flow
# exists for it) — it exists purely so the audit trail's agent_id FK
# resolves, while AuditLog.event_type="auto_resolved" is what actually
# marks the resolution as AI-only, not this account.
SYSTEM_USER_EMAIL = "system@resolveiq.internal"


# `SessionLocal`'s async engine (app/db/base.py) is a module-level singleton
# whose pooled asyncpg connections are bound to whichever event loop created
# them. `asyncio.run()` spins up and tears down a brand-new loop per call, so
# a second task reusing a pooled connection from the first task's (now
# closed) loop raised "RuntimeError: Event loop is closed" — the worker's
# very next ticket after any successful one silently failed. One loop for
# the worker process's lifetime keeps the pool valid across tasks, mirroring
# how uvicorn's single persistent loop already works on the API side. Safe
# under Celery's `--pool=solo` (the Windows-required pool, see README) since
# that's one process, one thread, running tasks sequentially.
_loop = asyncio.new_event_loop()


async def _record_failure(db: AsyncSession, ticket_id: str, exc: BaseException) -> None:
    # First line only, truncated: SQLAlchemy errors embed the whole failing
    # statement and its bound parameters in str(exc), which has no business
    # being copied wholesale into an audit row.
    first_line = (str(exc).splitlines() or [""])[0][:300]
    db.add(
        AuditLog(
            ticket_id=uuid.UUID(ticket_id),
            event_type="pipeline_failed",
            detail={"error_type": type(exc).__name__, "error": first_line},
            actor="system",
        )
    )
    await db.commit()


class _ProcessTicketTask(celery_app.Task):
    """Turns a final, retries-exhausted failure into an audit-log entry.

    Without this a failed task left no trace anywhere: the ticket just sat at
    "new" forever and the only evidence was a traceback in a worker log
    nobody was reading (docs/checkpoints/phase-7.md, the lost-task
    incident). on_failure fires only after autoretry gives up, not on each
    retry.
    """

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        async def _write() -> None:
            async with SessionLocal() as db:
                await _record_failure(db, args[0], exc)

        try:
            _loop.run_until_complete(_write())
        except Exception:
            logger.exception("Could not record pipeline failure for ticket %s", args[0])


# Bounded retries with backoff (5s, 10s, 20s, capped at 60s) for transient
# failures - a Groq/Hugging Face blip, a dropped DB connection. Deliberately
# NOT acks_late: on a 512MB free-tier worker, a task that OOM-kills the
# process would be redelivered and kill it again, turning one bad ticket
# into a crash loop that blocks every other ticket behind it.
@celery_app.task(
    name="process_ticket",
    base=_ProcessTicketTask,
    autoretry_for=(Exception,),
    retry_backoff=5,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def process_ticket(ticket_id: str) -> None:
    _loop.run_until_complete(_process_ticket_async(ticket_id))


async def _process_ticket_async(ticket_id: str) -> None:
    async with SessionLocal() as db:
        ticket = await db.get(Ticket, uuid.UUID(ticket_id))
        if ticket is None:
            return

        state = await run_pipeline(
            db, ticket.raw_text, ticket.id, ticket.customer_id, ticket.created_at
        )
        draft_result = state["draft_result"]
        decision = state["decision"]
        chunks = state.get("chunks") or []
        avg_retrieval_similarity = (
            sum(c.similarity for c in chunks) / len(chunks) if chunks else None
        )

        ticket.redacted_text = state["redacted_text"]
        ticket.category = state["category"]
        ticket.urgency_score = state["urgency_score"]
        ticket.breach_risk_score = state["breach_risk_score"]
        # "drafted" only when a real draft exists; a fallback/no-context
        # result stays "classified" so the queue can distinguish the two.
        # An auto-resolved ticket (below) overrides this to "resolved".
        ticket.status = "drafted" if draft_result.tier in ("cheap", "strong") else "classified"

        db.add(
            TicketDraft(
                ticket_id=ticket.id,
                draft_text=draft_result.draft_text,
                confidence=draft_result.confidence,
                source_chunk_ids=[uuid.UUID(cid) for cid in draft_result.source_chunk_ids],
                fast_path_eligible=decision.fast_path_eligible,
            )
        )

        db.add(
            AuditLog(
                ticket_id=ticket.id,
                event_type="drafted",
                detail={
                    "category": state["category"],
                    "category_confidence": state["category_confidence"],
                    "avg_retrieval_similarity": avg_retrieval_similarity,
                    "urgency_score": state["urgency_score"],
                    "urgency_confidence": state["urgency_confidence"],
                    "breach_risk_score": state["breach_risk_score"],
                    "draft_tier": draft_result.tier,
                    "draft_confidence": draft_result.confidence,
                    "source_chunk_ids": draft_result.source_chunk_ids,
                    "needs_review": decision.needs_review,
                    "specialist_flagged": decision.specialist_flagged,
                    "fast_path_eligible": decision.fast_path_eligible,
                    "decision_reason": decision.reason,
                },
                actor="system",
            )
        )

        # AUTO_RESOLVE_THRESHOLD (off by default, see docs/checkpoints/phase-7.md)
        # — the only path that ever resolves a ticket with no human agent.
        # Logged as a distinct event_type, never folded into "drafted" or
        # a normal agent "approved" event, so the audit trail always shows
        # whether a human was involved.
        if decision.auto_resolved:
            system_user = (
                await db.execute(select(User).where(User.email == SYSTEM_USER_EMAIL))
            ).scalar_one_or_none()
            if system_user is None:
                raise RuntimeError(
                    f"AUTO_RESOLVE_THRESHOLD is set but the sentinel system user "
                    f"({SYSTEM_USER_EMAIL}) doesn't exist — run "
                    f"app.scripts.seed_portal_demo first."
                )

            ticket.status = "resolved"
            db.add(
                TicketResolution(
                    ticket_id=ticket.id,
                    final_text=draft_result.draft_text,
                    action="approved",
                    agent_id=system_user.id,
                )
            )
            db.add(
                AuditLog(
                    ticket_id=ticket.id,
                    event_type="auto_resolved",
                    detail={
                        "resolved_by": "ai_auto",
                        "draft_confidence": draft_result.confidence,
                        "auto_resolve_threshold": settings.auto_resolve_threshold,
                        "decision_reason": decision.reason,
                    },
                    actor="system",
                )
            )

        await db.commit()
