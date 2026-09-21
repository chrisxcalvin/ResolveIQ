import uuid
from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_role
from app.db.base import get_db
from app.models.audit_log import AuditLog
from app.models.correction_signal import CorrectionSignal
from app.models.customer import Customer
from app.models.kb import KbChunk, KbDocument
from app.models.ticket import Ticket
from app.models.ticket_draft import TicketDraft
from app.models.ticket_resolution import TicketResolution
from app.models.user import User
from app.retrieval.retrieve import (
    APPROVE_BOOST_FACTOR,
    CORRECTION_BOOST_FACTOR,
    adjust_retrieval_boost,
)
from app.schemas.ticket import (
    CustomerHistoryItem,
    DraftOut,
    ResolveRequest,
    ResolveResponse,
    SourceOut,
    TicketCreate,
    TicketDetail,
    TicketListItem,
    TicketOut,
)
from app.tasks import process_ticket

router = APIRouter(prefix="/tickets", tags=["tickets"])

HISTORY_LOOKBACK = 5


@router.post("", response_model=TicketOut, status_code=201)
async def submit_ticket(
    payload: TicketCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("agent", "admin")),
) -> Ticket:
    result = await db.execute(
        select(Customer).where(Customer.masked_identifier == payload.customer_masked_identifier)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        customer = Customer(masked_identifier=payload.customer_masked_identifier)
        db.add(customer)
        await db.flush()

    ticket = Ticket(
        customer_id=customer.id,
        channel=payload.channel,
        raw_text=payload.raw_text,
        status="new",
    )
    db.add(ticket)
    await db.flush()

    db.add(
        AuditLog(
            ticket_id=ticket.id,
            event_type="submitted",
            detail={"channel": payload.channel},
            actor=str(user.id),
        )
    )
    await db.commit()
    await db.refresh(ticket)

    # Async processing (classify -> retrieve -> draft -> decide) — the API
    # returns immediately, per the App Flow's ticket lifecycle.
    process_ticket.delay(str(ticket.id))

    return ticket


@router.get("", response_model=list[TicketListItem])
async def list_tickets(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("agent", "admin")),
) -> list[TicketListItem]:
    # Breach-risk score (Feature 3) takes priority when present; tickets that
    # haven't been scored yet (still processing, or the model was
    # unavailable) fall back to urgency — the App Flow's documented
    # fallback behavior for when breach-risk scoring is unavailable.
    stmt = (
        select(Ticket, Customer.masked_identifier)
        .join(Customer, Ticket.customer_id == Customer.id)
        .order_by(
            Ticket.breach_risk_score.desc().nulls_last(),
            Ticket.urgency_score.desc().nulls_last(),
            Ticket.created_at.desc(),
        )
    )
    rows = (await db.execute(stmt)).all()
    return [
        TicketListItem(
            id=t.id,
            customer_masked_identifier=masked_id,
            channel=t.channel,
            category=t.category,
            urgency_score=t.urgency_score,
            breach_risk_score=t.breach_risk_score,
            status=t.status,
            created_at=t.created_at,
        )
        for t, masked_id in rows
    ]


@router.get("/{ticket_id}", response_model=TicketDetail)
async def get_ticket(
    ticket_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role("agent", "admin")),
) -> TicketDetail:
    row = (
        await db.execute(
            select(Ticket, Customer.masked_identifier)
            .join(Customer, Ticket.customer_id == Customer.id)
            .where(Ticket.id == ticket_id)
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket, masked_id = row

    latest_draft = (
        (
            await db.execute(
                select(TicketDraft)
                .where(TicketDraft.ticket_id == ticket_id)
                .order_by(TicketDraft.created_at.desc())
            )
        )
        .scalars()
        .first()
    )

    draft_out = None
    if latest_draft is not None:
        sources: list[SourceOut] = []
        if latest_draft.source_chunk_ids:
            chunk_rows = (
                await db.execute(
                    select(KbChunk, KbDocument.title)
                    .join(KbDocument, KbChunk.document_id == KbDocument.id)
                    .where(KbChunk.id.in_(latest_draft.source_chunk_ids))
                )
            ).all()
            sources = [
                SourceOut(chunk_id=chunk.id, document_title=title, content=chunk.content)
                for chunk, title in chunk_rows
            ]
        draft_out = DraftOut(
            id=latest_draft.id,
            draft_text=latest_draft.draft_text,
            confidence=latest_draft.confidence,
            sources=sources,
        )

    history_rows = (
        (
            await db.execute(
                select(Ticket)
                .where(Ticket.customer_id == ticket.customer_id, Ticket.id != ticket_id)
                .order_by(Ticket.created_at.desc())
                .limit(HISTORY_LOOKBACK)
            )
        )
        .scalars()
        .all()
    )

    # decide()'s verdict is only ever written into audit_log.detail (the
    # "drafted" event, see app/tasks.py) — it never lands on the ticket row
    # itself, so an agent reviewing the ticket had no way to see the
    # system's own "needs specialist review" judgment, only the raw
    # confidence number. Pull it back out here rather than duplicating it
    # onto Ticket.
    latest_drafted_event = (
        await db.execute(
            select(AuditLog)
            .where(AuditLog.ticket_id == ticket_id, AuditLog.event_type == "drafted")
            .order_by(AuditLog.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    specialist_flagged = False
    decision_reason = None
    category_confidence = None
    avg_retrieval_similarity = None
    if latest_drafted_event is not None:
        specialist_flagged = bool(latest_drafted_event.detail.get("specialist_flagged", False))
        decision_reason = latest_drafted_event.detail.get("decision_reason")
        category_confidence = latest_drafted_event.detail.get("category_confidence")
        avg_retrieval_similarity = latest_drafted_event.detail.get("avg_retrieval_similarity")

    return TicketDetail(
        id=ticket.id,
        customer_id=ticket.customer_id,
        customer_masked_identifier=masked_id,
        channel=ticket.channel,
        raw_text=ticket.raw_text,
        redacted_text=ticket.redacted_text,
        category=ticket.category,
        urgency_score=ticket.urgency_score,
        breach_risk_score=ticket.breach_risk_score,
        status=ticket.status,
        created_at=ticket.created_at,
        draft=draft_out,
        customer_history=[
            CustomerHistoryItem(
                id=h.id, category=h.category, status=h.status, created_at=h.created_at
            )
            for h in history_rows
        ],
        specialist_flagged=specialist_flagged,
        decision_reason=decision_reason,
        category_confidence=category_confidence,
        avg_retrieval_similarity=avg_retrieval_similarity,
    )


@router.post("/{ticket_id}/resolve", response_model=ResolveResponse)
async def resolve_ticket(
    ticket_id: uuid.UUID,
    payload: ResolveRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_role("agent", "admin")),
) -> ResolveResponse:
    # FOR UPDATE: holds the row lock for the rest of this transaction (until
    # commit/rollback below), so a second concurrent resolve on the same
    # ticket blocks here rather than racing past this check — without the
    # lock, two requests could both read status="drafted" before either
    # commits, and both would proceed.
    ticket = await db.get(Ticket, ticket_id, with_for_update=True)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status in ("resolved", "escalated"):
        raise HTTPException(
            status_code=409,
            detail=f"Ticket is already {ticket.status} — cannot resolve it again",
        )

    draft = (
        (
            await db.execute(
                select(TicketDraft)
                .where(TicketDraft.ticket_id == ticket_id)
                .order_by(TicketDraft.created_at.desc())
            )
        )
        .scalars()
        .first()
    )

    if payload.action in ("approve", "edit") and draft is None:
        raise HTTPException(status_code=400, detail="No draft available to approve or edit")

    # Snapshot the reasoning that produced the draft alongside the human's
    # verdict on it, so an audit-log reader can reconstruct "why" without
    # having to join back to the ticket and draft rows themselves
    # (05_Backend_Schema.md: audit_log.detail holds the full reasoning
    # snapshot). Titles rather than chunk UUIDs, since this is read by a human.
    cited_titles: list[str] = []
    if draft is not None and draft.source_chunk_ids:
        cited_titles = list(
            (
                await db.execute(
                    select(KbDocument.title)
                    .join(KbChunk, KbChunk.document_id == KbDocument.id)
                    .where(KbChunk.id.in_(draft.source_chunk_ids))
                    .distinct()
                )
            ).scalars()
        )

    audit_detail: dict = {
        "action": payload.action,
        "category": ticket.category,
        "urgency_score": ticket.urgency_score,
        "breach_risk_score": ticket.breach_risk_score,
        "status_before": ticket.status,
        "draft_confidence": draft.confidence if draft else None,
        "cited_sources": cited_titles,
        "cited_chunk_count": len(draft.source_chunk_ids or []) if draft else 0,
    }

    if payload.action == "approve":
        final_text = draft.draft_text
        ticket.status = "resolved"
        db.add(
            TicketResolution(
                ticket_id=ticket.id, final_text=final_text, action="approved", agent_id=user.id
            )
        )
        # Sources cited in an unmodified, approved draft did their job.
        await adjust_retrieval_boost(db, draft.source_chunk_ids or [], corrected=False)
        audit_detail["retrieval_boost_effect"] = (
            f"promoted {len(draft.source_chunk_ids or [])} cited chunk(s) "
            f"x{APPROVE_BOOST_FACTOR}"
        )

    elif payload.action == "edit":
        if not payload.final_text or not payload.final_text.strip():
            raise HTTPException(status_code=400, detail="final_text is required for an edit")
        final_text = payload.final_text
        edit_distance = 1 - SequenceMatcher(None, draft.draft_text, final_text).ratio()

        ticket.status = "resolved"
        db.add(
            TicketResolution(
                ticket_id=ticket.id,
                final_text=final_text,
                action="edited",
                agent_id=user.id,
                edit_distance=edit_distance,
            )
        )
        db.add(
            CorrectionSignal(
                ticket_id=ticket.id,
                draft_id=draft.id,
                diff_summary=f"{edit_distance:.0%} of the draft text changed on edit",
                affected_chunk_ids=draft.source_chunk_ids,
            )
        )
        # Feedback loop (App Flow step 7): the cited sources weren't
        # sufficient on their own — demote them for future retrieval.
        await adjust_retrieval_boost(db, draft.source_chunk_ids or [], corrected=True)
        audit_detail["edit_distance"] = edit_distance
        audit_detail["diff_summary"] = f"{edit_distance:.0%} of the draft text changed on edit"
        audit_detail["retrieval_boost_effect"] = (
            f"demoted {len(draft.source_chunk_ids or [])} cited chunk(s) "
            f"x{CORRECTION_BOOST_FACTOR} — these rank lower for future similar tickets"
        )

    else:  # escalate
        # ticket_resolutions.final_text is NOT NULL even for escalations —
        # store whatever text was in play (an agent edit if given, else the
        # AI draft if one exists) as the record of what was on screen at
        # escalation time, since nothing was actually sent to the customer.
        final_text = payload.final_text or (draft.draft_text if draft else "")
        ticket.status = "escalated"
        db.add(
            TicketResolution(
                ticket_id=ticket.id,
                final_text=final_text,
                action="escalated",
                agent_id=user.id,
                escalation_note=payload.escalation_note,
            )
        )
        audit_detail["escalation_note"] = payload.escalation_note
        audit_detail["retrieval_boost_effect"] = (
            "none — escalation says the ticket was out of scope for the draft, "
            "not that the cited sources were wrong"
        )

    db.add(
        AuditLog(
            ticket_id=ticket.id,
            event_type=payload.action,
            detail=audit_detail,
            actor=str(user.id),
        )
    )

    await db.commit()
    return ResolveResponse(id=ticket.id, status=ticket.status, action=payload.action)
