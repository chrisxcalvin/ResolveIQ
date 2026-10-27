"""Phase 8 benchmarking: a real time-to-draft distribution, measured by
submitting real CFPB-derived tickets through the actual Celery pipeline —
process_ticket.delay(), the exact same call submit_ticket() makes — and
reading back real Ticket.created_at / TicketDraft.created_at timestamps.
No estimate, no synthetic timing.

Tickets are submitted ONE AT A TIME, each one waited out to completion
before the next is submitted. This measures per-ticket pipeline service
time specifically, not queue-wait time inflated by this script's own
batch-submission pattern — a real concurrent-arrival queueing effect is a
genuine thing (the deployed worker is single-threaded by necessity, see
docs/checkpoints/phase-5.md's --pool=solo note), but conflating "my own
benchmark script dumped 30 tickets at once" with "the pipeline is slow"
would misrepresent what's actually being measured.

Requires a running Celery worker on the SAME broker configured in .env
(`uv run celery -A app.worker worker --loglevel=info --pool=solo`) — this
creates real rows in the real configured database and makes real Groq/
classifier calls, exactly like a real submitted ticket would.

Usage: uv run python -m app.scripts.benchmark_time_to_draft [N]
Writes results to app/ml/artifacts/benchmark_time_to_draft.json
"""

import asyncio
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.db.base import SessionLocal
from app.ml.cfpb_data import load as load_cfpb
from app.models.audit_log import AuditLog
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.ticket_draft import TicketDraft
from app.tasks import process_ticket

BENCHMARK_CUSTOMER_IDENTIFIER = "benchmark_phase8"
DEFAULT_N = 30
POLL_INTERVAL_S = 2
PER_TICKET_TIMEOUT_S = 120
OUT_PATH = Path(__file__).parent.parent / "ml" / "artifacts" / "benchmark_time_to_draft.json"


async def _get_or_create_benchmark_customer(db) -> Customer:
    existing = (
        await db.execute(select(Customer).where(Customer.masked_identifier == BENCHMARK_CUSTOMER_IDENTIFIER))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    customer = Customer(masked_identifier=BENCHMARK_CUSTOMER_IDENTIFIER)
    db.add(customer)
    await db.flush()
    await db.commit()
    return customer


def _pick_complaints(n: int) -> list:
    complaints = load_cfpb()
    by_cat: dict[str, list] = {}
    for c in complaints:
        if 80 <= len(c.text) <= 600:
            by_cat.setdefault(c.category, []).append(c)
    cats = sorted(by_cat)
    picked = []
    i = 0
    while len(picked) < n and any(by_cat.values()):
        cat = cats[i % len(cats)]
        if by_cat[cat]:
            picked.append(by_cat[cat].pop())
        i += 1
    return picked[:n]


async def _run_one(db, customer_id, raw_text: str, category_hint: str) -> dict:
    ticket = Ticket(customer_id=customer_id, channel="benchmark", raw_text=raw_text, status="new")
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)  # picks up the real server-computed created_at
    submitted_at = ticket.created_at
    ticket_id = ticket.id

    process_ticket.delay(str(ticket_id))

    deadline = time.monotonic() + PER_TICKET_TIMEOUT_S
    while time.monotonic() < deadline:
        await asyncio.sleep(POLL_INTERVAL_S)
        draft = (
            await db.execute(
                select(TicketDraft).where(TicketDraft.ticket_id == ticket_id).order_by(TicketDraft.created_at.desc())
            )
        ).scalars().first()
        if draft is not None:
            delta = (draft.created_at - submitted_at).total_seconds()
            drafted_event = (
                await db.execute(
                    select(AuditLog)
                    .where(AuditLog.ticket_id == ticket_id, AuditLog.event_type == "drafted")
                    .order_by(AuditLog.created_at.desc())
                )
            ).scalars().first()
            tier = drafted_event.detail.get("draft_tier") if drafted_event else None
            specialist_reviewed = bool(drafted_event.detail.get("specialist_reviewed")) if drafted_event else False
            return {
                "ticket_id": str(ticket_id),
                "category_hint": category_hint,
                "seconds": delta,
                "tier": tier,
                "specialist_reviewed": specialist_reviewed,
                "timed_out": False,
            }
    return {"ticket_id": str(ticket_id), "category_hint": category_hint, "seconds": None, "timed_out": True}


async def run_batch(n: int) -> list[dict]:
    complaints = _pick_complaints(n)
    results = []
    async with SessionLocal() as db:
        customer = await _get_or_create_benchmark_customer(db)
        for i, c in enumerate(complaints, 1):
            print(f"[{i}/{len(complaints)}] submitting a {c.category} ticket...", flush=True)
            r = await _run_one(db, customer.id, c.text, c.category)
            if r["timed_out"]:
                print(f"  TIMED OUT after {PER_TICKET_TIMEOUT_S}s")
            else:
                print(f"  draft ready in {r['seconds']:.2f}s")
            results.append(r)

    completed = sorted(r["seconds"] for r in results if not r["timed_out"])
    summary = {}
    if completed:
        n_r = len(completed)
        median = completed[n_r // 2] if n_r % 2 else (completed[n_r // 2 - 1] + completed[n_r // 2]) / 2
        p95 = completed[min(n_r - 1, int(0.95 * n_r))]
        summary = {
            "n_completed": n_r,
            "n_timed_out": len(results) - n_r,
            "median_seconds": round(median, 2),
            "p95_seconds": round(p95, 2),
            "min_seconds": round(completed[0], 2),
            "max_seconds": round(completed[-1], 2),
        }
        print(
            f"\nn={n_r} completed, {summary['n_timed_out']} timed out  "
            f"median={median:.2f}s  p95={p95:.2f}s  min={completed[0]:.2f}s  max={completed[-1]:.2f}s"
        )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as f:
        json.dump(
            {
                "measured_at": datetime.now(timezone.utc).isoformat(),
                "n_requested": n,
                "per_ticket": results,
                "summary": summary,
            },
            f,
            indent=2,
        )
    print(f"\nWrote {OUT_PATH}")
    return results


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_N
    asyncio.run(run_batch(n))
