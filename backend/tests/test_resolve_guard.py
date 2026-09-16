"""Phase 2: the double-resolve guard added in Phase 1
(app/api/routes/tickets.py::resolve_ticket), exercised at the HTTP layer —
auth -> ticket -> resolve -> real status code, not a unit-level check.
"""

import pytest

from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.ticket_draft import TicketDraft


async def _make_ticket(db_session, status: str, *, with_draft: bool = False) -> Ticket:
    customer = Customer(masked_identifier=f"cust_test_{status}")
    db_session.add(customer)
    await db_session.flush()

    ticket = Ticket(
        customer_id=customer.id,
        channel="email",
        raw_text="raw",
        redacted_text="redacted",
        status=status,
        category="general_query",
        urgency_score=0.2,
    )
    db_session.add(ticket)
    await db_session.flush()

    if with_draft:
        db_session.add(
            TicketDraft(
                ticket_id=ticket.id,
                draft_text="a grounded reply",
                confidence=0.8,
                source_chunk_ids=[],
            )
        )
        await db_session.flush()

    return ticket


@pytest.mark.asyncio
async def test_cannot_approve_an_already_resolved_ticket(client, db_session, auth_headers):
    ticket = await _make_ticket(db_session, status="resolved")

    resp = await client.post(
        f"/tickets/{ticket.id}/resolve", json={"action": "approve"}, headers=auth_headers
    )
    assert resp.status_code == 409
    assert "already resolved" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cannot_escalate_an_already_escalated_ticket(client, db_session, auth_headers):
    ticket = await _make_ticket(db_session, status="escalated")

    resp = await client.post(
        f"/tickets/{ticket.id}/resolve",
        json={"action": "escalate", "escalation_note": "second attempt"},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert "already escalated" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_cannot_edit_an_already_resolved_ticket(client, db_session, auth_headers):
    """The guard must apply to all three actions, not just approve."""
    ticket = await _make_ticket(db_session, status="resolved")

    resp = await client.post(
        f"/tickets/{ticket.id}/resolve",
        json={"action": "edit", "final_text": "a different reply"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_can_still_approve_a_normal_drafted_ticket(client, db_session, auth_headers):
    """Sanity check the guard doesn't over-trigger on the happy path."""
    ticket = await _make_ticket(db_session, status="drafted", with_draft=True)

    resp = await client.post(
        f"/tickets/{ticket.id}/resolve", json={"action": "approve"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "resolved"
