"""process_ticket failure handling (app/tasks.py).

Regression coverage for the lost-task incident: a task that failed used to
leave no trace at all - the ticket sat at "new" forever. Now a final
failure is recorded in the audit log, and transient failures are retried
a bounded number of times first.
"""

from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.tasks import _record_failure, process_ticket


async def _make_ticket(db) -> Ticket:
    customer = Customer(masked_identifier="cust_failure_test")
    db.add(customer)
    await db.flush()
    ticket = Ticket(customer_id=customer.id, channel="email", raw_text="x", status="new")
    db.add(ticket)
    await db.flush()
    return ticket


async def _failure_events(db, ticket) -> list[AuditLog]:
    result = await db.execute(
        select(AuditLog).where(
            AuditLog.ticket_id == ticket.id, AuditLog.event_type == "pipeline_failed"
        )
    )
    return list(result.scalars().all())


async def test_final_failure_is_recorded_in_the_audit_log(db_session):
    ticket = await _make_ticket(db_session)

    await _record_failure(db_session, str(ticket.id), RuntimeError("groq is down"))

    (event,) = await _failure_events(db_session, ticket)
    assert event.detail == {"error_type": "RuntimeError", "error": "groq is down"}
    assert event.actor == "system"


async def test_recorded_error_is_first_line_only_and_truncated(db_session):
    """SQLAlchemy errors embed the whole failing SQL statement and its bound
    parameters in str(exc) - that must not be copied into an audit row."""
    ticket = await _make_ticket(db_session)
    noisy = "connection was closed\n[SQL: SELECT ...]\n[parameters: ('private',)]" + "x" * 500

    await _record_failure(db_session, str(ticket.id), RuntimeError(noisy))

    (event,) = await _failure_events(db_session, ticket)
    assert event.detail["error"] == "connection was closed"
    assert "private" not in str(event.detail)


async def test_long_single_line_error_is_capped(db_session):
    ticket = await _make_ticket(db_session)

    await _record_failure(db_session, str(ticket.id), RuntimeError("y" * 1000))

    (event,) = await _failure_events(db_session, ticket)
    assert len(event.detail["error"]) == 300


def test_task_retries_transient_failures_a_bounded_number_of_times():
    assert process_ticket.autoretry_for == (Exception,)
    assert process_ticket.max_retries == 3
    assert process_ticket.retry_backoff_max == 60


def test_task_is_not_acks_late():
    """acks_late would redeliver a task that OOM-kills the 512MB worker,
    turning one bad ticket into a crash loop that blocks the whole queue."""
    assert process_ticket.acks_late is not True
