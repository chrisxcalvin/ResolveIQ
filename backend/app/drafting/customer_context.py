"""Feature 2: customer-history summary injected into the drafting agent's
prompt. Per 05_Backend_Schema.md, `customer_id` on `tickets` is the entire
mechanism — no separate service, just a join + a summarization step here.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ticket import Ticket
from app.models.ticket_resolution import TicketResolution

HISTORY_LOOKBACK = 5


async def build_customer_history_summary(
    db: AsyncSession, customer_id: uuid.UUID, exclude_ticket_id: uuid.UUID
) -> str:
    """Returns a short plain-text summary of the customer's other tickets,
    or "" for a first-time customer (nothing to add to the prompt).
    """
    stmt = (
        select(Ticket.category, Ticket.status, TicketResolution.action)
        .outerjoin(TicketResolution, TicketResolution.ticket_id == Ticket.id)
        .where(Ticket.customer_id == customer_id, Ticket.id != exclude_ticket_id)
        .order_by(Ticket.created_at.desc())
        .limit(HISTORY_LOOKBACK)
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return ""

    lines = []
    for category, status, action in rows:
        category = category or "uncategorized"
        outcome = action or status
        lines.append(f"{category} ({outcome})")

    return f"Returning customer — {len(rows)} prior ticket(s): " + ", ".join(lines) + "."
