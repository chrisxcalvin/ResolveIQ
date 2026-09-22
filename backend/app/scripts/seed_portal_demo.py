"""Seeds Phase 7 customer-portal demo state: a sentinel "system" user (the
AUTO_RESOLVE_THRESHOLD actor — see app/tasks.py's SYSTEM_USER_EMAIL) and
8-10 demo customers with a display name, account reference, and 2-3 past
resolved tickets each, so the portal's customer picker has something real
to show and each demo customer has genuine history for the pipeline's
customer-context step to draw on.

Resolved history reuses real CFPB-derived complaint narratives (Phase 3's
cached dataset) rather than hand-written text, picked per-category so each
demo customer's history matches their assigned "personality" (a payments
issue, an account-lock issue, etc). Written directly rather than through
the pipeline — same reasoning as app/scripts/seed_demo.py: exact
classification of already-resolved history doesn't matter, only that it
exists for retrieval/context.

Usage: uv run python -m app.scripts.seed_portal_demo
(requires the CFPB cache — see README's "Seeding & training" section, or
run `uv run python -m app.ml.cfpb_data` first)
"""

import asyncio
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import SessionLocal
from app.ml.cfpb_data import load as load_cfpb
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.ticket_resolution import TicketResolution
from app.models.user import User
from app.tasks import SYSTEM_USER_EMAIL

# DEMO_CUSTOMERS: (display_name, account_reference, category to pull resolved
# history from). Category here only picks which real CFPB narratives this
# customer's history uses — it has no bearing on what they can submit later.
DEMO_CUSTOMERS = [
    ("Jordan Alvarez", "acct-48213", "payment_failure"),
    ("Priya Natarajan", "acct-77410", "refund_delay"),
    ("Marcus Webb", "acct-19924", "account_lock"),
    ("Sofia Petrov", "acct-63302", "dispute"),
    ("Devon Clarke", "acct-50187", "general_query"),
    ("Amara Okafor", "acct-91456", "payment_failure"),
    ("Liam Fitzgerald", "acct-33765", "refund_delay"),
    ("Yuki Tanaka", "acct-28840", "account_lock"),
    ("Elena Vasquez", "acct-70129", "dispute"),
    ("Noah Bergström", "acct-44573", "general_query"),
]

HISTORY_PER_CUSTOMER = 3
MIN_TEXT_LEN = 80
MAX_TEXT_LEN = 400


async def seed_portal_demo() -> None:
    complaints = load_cfpb()
    by_category: dict[str, list] = {}
    for c in complaints:
        if MIN_TEXT_LEN <= len(c.text) <= MAX_TEXT_LEN:
            by_category.setdefault(c.category, []).append(c)

    used_ids: set[str] = set()

    def _pick(category: str, n: int) -> list[str]:
        pool = by_category.get(category, [])
        picked = []
        for c in pool:
            if c.complaint_id in used_ids:
                continue
            picked.append(c.text)
            used_ids.add(c.complaint_id)
            if len(picked) == n:
                break
        return picked

    async with SessionLocal() as db:
        system_user = (
            await db.execute(select(User).where(User.email == SYSTEM_USER_EMAIL))
        ).scalar_one_or_none()
        if system_user is None:
            system_user = User(
                email=SYSTEM_USER_EMAIL,
                # Random, never used to log in — see SYSTEM_USER_EMAIL's docstring in app/tasks.py.
                password_hash=hash_password(secrets.token_urlsafe(32)),
                role="admin",
            )
            db.add(system_user)
            await db.flush()
            print(f"Created sentinel system user {SYSTEM_USER_EMAIL}")
        else:
            print(f"Sentinel system user {SYSTEM_USER_EMAIL} already exists, reusing.")

        for display_name, account_reference, category in DEMO_CUSTOMERS:
            existing = (
                await db.execute(
                    select(Customer).where(Customer.display_name == display_name)
                )
            ).scalar_one_or_none()
            if existing is not None:
                print(f"Demo customer {display_name!r} already exists, skipping.")
                continue

            customer = Customer(
                masked_identifier=f"portal_{account_reference}",
                display_name=display_name,
                account_reference=account_reference,
            )
            db.add(customer)
            await db.flush()

            texts = _pick(category, HISTORY_PER_CUSTOMER)
            for i, text in enumerate(texts):
                ticket = Ticket(
                    customer_id=customer.id,
                    channel="portal",
                    raw_text=text,
                    category=category,
                    urgency_score=0.3,
                    status="resolved",
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None)
                    - timedelta(days=30 - i * 7),
                )
                db.add(ticket)
                await db.flush()
                db.add(
                    TicketResolution(
                        ticket_id=ticket.id,
                        final_text="Resolved — see prior correspondence for details.",
                        action="approved",
                        agent_id=system_user.id,
                    )
                )

            await db.commit()
            print(f"Seeded {display_name!r} ({account_reference}) with {len(texts)} resolved ticket(s).")

    print()
    print(f"Portal demo ready — {len(DEMO_CUSTOMERS)} demo customers seeded (or already present).")


if __name__ == "__main__":
    asyncio.run(seed_portal_demo())
