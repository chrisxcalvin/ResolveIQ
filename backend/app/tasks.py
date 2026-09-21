"""Celery task: runs a ticket through the full AI pipeline."""

import asyncio
import uuid

from app.db.base import SessionLocal
from app.models.audit_log import AuditLog
from app.models.ticket import Ticket
from app.models.ticket_draft import TicketDraft
from app.pipeline.graph import run_pipeline
from app.worker import celery_app


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


@celery_app.task(name="process_ticket")
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
        ticket.status = "drafted" if draft_result.tier in ("cheap", "strong") else "classified"

        db.add(
            TicketDraft(
                ticket_id=ticket.id,
                draft_text=draft_result.draft_text,
                confidence=draft_result.confidence,
                source_chunk_ids=[uuid.UUID(cid) for cid in draft_result.source_chunk_ids],
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
                    "decision_reason": decision.reason,
                },
                actor="system",
            )
        )

        await db.commit()
