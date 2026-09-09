"""Seeds realistic demo state: a demo user, a returning customer with
resolved history (Feature 2 context), and a handful of fresh tickets run
through the real pipeline so they show up classified/drafted/breach-scored
in the queue exactly like production traffic would.

Does NOT pre-bake the correction-improves-next-draft sequence — that's the
live, interactive part of the demo (see DEMO.md). This script only sets the
stage.

Usage: uv run python -m app.scripts.seed_demo
(requires KB + classifiers already trained/embedded — see README's
"Seeding & training" section)
"""

import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import SessionLocal
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.ticket_draft import TicketDraft
from app.models.ticket_resolution import TicketResolution
from app.models.user import User
from app.tasks import _process_ticket_async

DEMO_EMAIL = "demo@resolveiq.io"
DEMO_PASSWORD = "resolveiq-demo"

RETURNING_CUSTOMER_ID = "cust_demo_returning"
NEW_CUSTOMER_ID = "cust_demo_firsttime"

# (raw_text, channel) — run through the real pipeline so category, urgency,
# breach_risk_score, and the draft are all genuine model output.
FRESH_TICKETS = [
    (
        RETURNING_CUSTOMER_ID,
        "email",
        "I don't recognize a $340 charge on my account, I think someone else "
        "used my card. I need this looked at right away, it's my rent money.",
    ),
    (
        NEW_CUSTOMER_ID,
        "chat",
        "I was charged twice for the same order this morning, can you refund "
        "the duplicate charge?",
    ),
    (
        NEW_CUSTOMER_ID,
        "form",
        "What are the fees listed on my monthly statement for?",
    ),
    (
        RETURNING_CUSTOMER_ID,
        "email",
        "My account just got locked and I can't log in at all, I need access "
        "today to pay a bill.",
    ),
]


async def _get_or_create_customer(db, masked_identifier: str) -> Customer:
    result = await db.execute(select(Customer).where(Customer.masked_identifier == masked_identifier))
    customer = result.scalar_one_or_none()
    if customer is None:
        customer = Customer(masked_identifier=masked_identifier)
        db.add(customer)
        await db.flush()
    return customer


async def seed_demo() -> None:
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == DEMO_EMAIL))).scalar_one_or_none()
        if user is None:
            user = User(email=DEMO_EMAIL, password_hash=hash_password(DEMO_PASSWORD), role="admin")
            db.add(user)
            await db.flush()
            print(f"Created demo user {DEMO_EMAIL} / {DEMO_PASSWORD}")
        else:
            print(f"Demo user {DEMO_EMAIL} already exists, reusing.")

        returning_customer = await _get_or_create_customer(db, RETURNING_CUSTOMER_ID)
        await _get_or_create_customer(db, NEW_CUSTOMER_ID)

        # Resolved history for the returning customer (Feature 2 context) —
        # written directly rather than through the pipeline since their
        # exact classification doesn't matter, only that history exists.
        history_count = (
            await db.execute(select(Ticket).where(Ticket.customer_id == returning_customer.id))
        ).scalars().all()
        if not history_count:
            old_ticket_1 = Ticket(
                customer_id=returning_customer.id,
                channel="email",
                raw_text="My refund from last month never showed up.",
                category="refund_delay",
                urgency_score=0.4,
                status="resolved",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=14),
            )
            old_ticket_2 = Ticket(
                customer_id=returning_customer.id,
                channel="chat",
                raw_text="Payment kept failing at checkout last week.",
                category="payment_failure",
                urgency_score=0.3,
                status="resolved",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=5),
            )
            db.add_all([old_ticket_1, old_ticket_2])
            await db.flush()
            db.add_all(
                [
                    TicketResolution(
                        ticket_id=old_ticket_1.id,
                        final_text="Refund was reissued and confirmed delivered.",
                        action="approved",
                        agent_id=user.id,
                    ),
                    TicketResolution(
                        ticket_id=old_ticket_2.id,
                        final_text="Walked customer through updating their expired card.",
                        action="edited",
                        agent_id=user.id,
                        edit_distance=0.4,
                    ),
                ]
            )
            await db.commit()
            print("Seeded resolved ticket history for the returning customer.")
        else:
            print("Returning customer already has history, skipping.")

        ticket_ids = []
        for masked_id, channel, raw_text in FRESH_TICKETS:
            customer = await _get_or_create_customer(db, masked_id)
            ticket = Ticket(customer_id=customer.id, channel=channel, raw_text=raw_text, status="new")
            db.add(ticket)
            await db.commit()
            await db.refresh(ticket)
            ticket_ids.append(ticket.id)

    # Run each ticket through the exact same code path production traffic
    # uses (app.tasks._process_ticket_async) — not a reimplementation, so
    # this can't drift from what actually happens on real ticket submission
    # (a prior version of this script did reimplement it, and forgot to
    # persist the TicketDraft row, leaving "drafted" tickets with no draft).
    print(f"Running {len(ticket_ids)} fresh tickets through the real pipeline...")
    for ticket_id in ticket_ids:
        await _process_ticket_async(str(ticket_id))

    async with SessionLocal() as db:
        for ticket_id in ticket_ids:
            ticket = await db.get(Ticket, ticket_id)
            draft = (
                await db.execute(select(TicketDraft).where(TicketDraft.ticket_id == ticket_id))
            ).scalar_one_or_none()
            print(
                f"  [{ticket.category}] urgency={ticket.urgency_score:.2f} "
                f"breach_risk={ticket.breach_risk_score:.2f} status={ticket.status} "
                f"has_draft={draft is not None} — {ticket.raw_text[:50]!r}"
            )

    print()
    print("Demo state ready. Log in at the frontend with:")
    print(f"  {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(seed_demo())
