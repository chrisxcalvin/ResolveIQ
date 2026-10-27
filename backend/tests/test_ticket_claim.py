"""Phase 9: ticket claim/assignment (app/api/routes/tickets.py::claim_ticket,
unclaim_ticket, and the enforcement added to resolve_ticket) — so two agents
can't work the same ticket blind. assigned_agent_id existed on the schema
since Phase 1 but nothing ever set or enforced it until this.
"""

import uuid

import pytest

from app.core.security import create_access_token, hash_password
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.ticket_draft import TicketDraft
from app.models.user import User


async def _make_ticket(db_session, *, with_draft: bool = True) -> Ticket:
    customer = Customer(masked_identifier=f"cust_{uuid.uuid4().hex[:8]}")
    db_session.add(customer)
    await db_session.flush()

    ticket = Ticket(
        customer_id=customer.id,
        channel="email",
        raw_text="raw",
        redacted_text="redacted",
        status="drafted",
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


async def _second_agent_headers(db_session) -> dict:
    user = User(
        email=f"agent2-{uuid.uuid4().hex[:8]}@test.local",
        password_hash=hash_password("testpass123"),
        role="agent",
    )
    db_session.add(user)
    await db_session.flush()
    token = create_access_token(user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_claim_sets_assigned_agent(client, db_session, auth_headers, agent_user):
    ticket = await _make_ticket(db_session)

    resp = await client.post(f"/tickets/{ticket.id}/claim", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["assigned_agent_id"] == str(agent_user.id)
    assert body["assigned_agent_email"] == agent_user.email


@pytest.mark.asyncio
async def test_claiming_an_already_claimed_ticket_by_another_agent_is_409(
    client, db_session, auth_headers
):
    ticket = await _make_ticket(db_session)
    other_headers = await _second_agent_headers(db_session)

    first = await client.post(f"/tickets/{ticket.id}/claim", headers=other_headers)
    assert first.status_code == 200

    second = await client.post(f"/tickets/{ticket.id}/claim", headers=auth_headers)
    assert second.status_code == 409
    assert "already claimed" in second.json()["detail"]


@pytest.mark.asyncio
async def test_claiming_your_own_already_claimed_ticket_is_idempotent(
    client, db_session, auth_headers, agent_user
):
    ticket = await _make_ticket(db_session)

    first = await client.post(f"/tickets/{ticket.id}/claim", headers=auth_headers)
    second = await client.post(f"/tickets/{ticket.id}/claim", headers=auth_headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["assigned_agent_id"] == str(agent_user.id)


@pytest.mark.asyncio
async def test_unclaim_releases_the_ticket(client, db_session, auth_headers):
    ticket = await _make_ticket(db_session)
    await client.post(f"/tickets/{ticket.id}/claim", headers=auth_headers)

    resp = await client.post(f"/tickets/{ticket.id}/unclaim", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "drafted"  # unclaim doesn't touch ticket status

    get_resp = await client.get(f"/tickets/{ticket.id}", headers=auth_headers)
    assert get_resp.json()["assigned_agent_id"] is None


@pytest.mark.asyncio
async def test_unclaiming_another_agents_ticket_is_409(client, db_session, auth_headers):
    ticket = await _make_ticket(db_session)
    other_headers = await _second_agent_headers(db_session)
    await client.post(f"/tickets/{ticket.id}/claim", headers=other_headers)

    resp = await client.post(f"/tickets/{ticket.id}/unclaim", headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_resolving_an_unclaimed_ticket_self_claims_it(client, db_session, auth_headers, agent_user):
    """The common single-step 'open it and approve' flow needs no separate
    claim call — resolving an unclaimed ticket silently claims it first."""
    ticket = await _make_ticket(db_session)

    resp = await client.post(
        f"/tickets/{ticket.id}/resolve", json={"action": "approve"}, headers=auth_headers
    )
    assert resp.status_code == 200

    get_resp = await client.get(f"/tickets/{ticket.id}", headers=auth_headers)
    assert get_resp.json()["assigned_agent_id"] == str(agent_user.id)


@pytest.mark.asyncio
async def test_cannot_resolve_a_ticket_claimed_by_another_agent(client, db_session, auth_headers):
    ticket = await _make_ticket(db_session)
    other_headers = await _second_agent_headers(db_session)
    await client.post(f"/tickets/{ticket.id}/claim", headers=other_headers)

    resp = await client.post(
        f"/tickets/{ticket.id}/resolve", json={"action": "approve"}, headers=auth_headers
    )
    assert resp.status_code == 409
    assert "claimed by another agent" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_can_resolve_a_ticket_you_claimed_yourself(client, db_session, auth_headers):
    ticket = await _make_ticket(db_session)
    await client.post(f"/tickets/{ticket.id}/claim", headers=auth_headers)

    resp = await client.post(
        f"/tickets/{ticket.id}/resolve", json={"action": "approve"}, headers=auth_headers
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_claiming_a_nonexistent_ticket_is_404(client, auth_headers):
    resp = await client.post(f"/tickets/{uuid.uuid4()}/claim", headers=auth_headers)
    assert resp.status_code == 404
