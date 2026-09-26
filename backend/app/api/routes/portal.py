"""Public, no-login customer portal (Phase 7) — deliberately minimal auth:
the picker only ever exposes seeded demo customers (`display_name IS NOT
NULL`), so a client-trusted `customer_id` carries no real risk even without
a token. Submits into the exact same pipeline app.api.routes.tickets uses —
no separate code path — and every response here is a customer-safe subset,
never the internal fields (confidence, specialist routing, cited sources)
the agent-facing schemas expose.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.worker_wake import wake_worker
from app.db.base import get_db
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.ticket_resolution import TicketResolution
from app.schemas.portal import (
    PortalCustomer,
    PortalTicketCreate,
    PortalTicketCreated,
    PortalTicketListItem,
    PortalTicketStatus,
)
from app.tasks import process_ticket

router = APIRouter(prefix="/portal", tags=["portal"])

HISTORY_LOOKBACK = 10


async def _get_demo_customer(db: AsyncSession, customer_id: uuid.UUID) -> Customer:
    customer = await db.get(Customer, customer_id)
    if customer is None or customer.display_name is None:
        # Same 404 whether the id doesn't exist or belongs to a real
        # (non-demo) customer — this boundary must never reveal which ids
        # are real vs demo.
        raise HTTPException(status_code=404, detail="Demo customer not found")
    return customer


@router.get("/customers", response_model=list[PortalCustomer])
async def list_demo_customers(db: AsyncSession = Depends(get_db)) -> list[Customer]:
    result = await db.execute(
        select(Customer)
        .where(Customer.display_name.is_not(None))
        .order_by(Customer.display_name)
    )
    return list(result.scalars().all())


@router.post("/tickets", response_model=PortalTicketCreated, status_code=201)
async def submit_portal_ticket(
    payload: PortalTicketCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> Ticket:
    customer = await _get_demo_customer(db, payload.customer_id)

    raw_text = f"{payload.subject.strip()}\n\n{payload.description.strip()}"
    ticket = Ticket(customer_id=customer.id, channel="portal", raw_text=raw_text, status="new")
    db.add(ticket)
    await db.flush()

    db.add(
        AuditLog(
            ticket_id=ticket.id,
            event_type="submitted",
            detail={"channel": "portal"},
            actor=f"customer:{customer.id}",
        )
    )
    await db.commit()
    await db.refresh(ticket)

    # Async processing, same code path submit_ticket() (agent side) uses —
    # the pipeline has no idea which channel a ticket came from.
    process_ticket.delay(str(ticket.id))
    background_tasks.add_task(wake_worker)

    return ticket


@router.get("/tickets/{ticket_id}", response_model=PortalTicketStatus)
async def get_portal_ticket(
    ticket_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> PortalTicketStatus:
    row = (
        await db.execute(
            select(Ticket, Customer.display_name)
            .join(Customer, Ticket.customer_id == Customer.id)
            .where(Ticket.id == ticket_id, Customer.display_name.is_not(None))
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    ticket, _ = row

    final_reply = None
    if ticket.status == "resolved":
        resolution = (
            await db.execute(
                select(TicketResolution)
                .where(TicketResolution.ticket_id == ticket_id)
                .order_by(TicketResolution.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if resolution is not None:
            final_reply = resolution.final_text

    return PortalTicketStatus(
        id=ticket.id,
        status=ticket.status,
        category=ticket.category,
        created_at=ticket.created_at,
        final_reply=final_reply,
    )


@router.get("/customers/{customer_id}/tickets", response_model=list[PortalTicketListItem])
async def list_customer_tickets(
    customer_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> list[Ticket]:
    await _get_demo_customer(db, customer_id)
    result = await db.execute(
        select(Ticket)
        .where(Ticket.customer_id == customer_id)
        .order_by(Ticket.created_at.desc())
        .limit(HISTORY_LOOKBACK)
    )
    return list(result.scalars().all())
