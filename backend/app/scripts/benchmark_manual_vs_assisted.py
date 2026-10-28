"""Phase 8 benchmarking: the manual-vs-assisted comparison, run BY A HUMAN
(see BUILD_SPEC.md Phase 8, item 2) — this script cannot fabricate this
data, it only makes running the real comparison as fast as possible to
actually sit through.

For each ticket (reusing the real tickets + real drafts from a prior
`benchmark_time_to_draft` run, so the pipeline isn't run twice):
  1. Shows ONLY the customer's raw ticket text (no AI draft) and times how
     long it takes you to look up the answer in backend/app/kb/articles/
     yourself and write a reply from what you find — simulating an agent
     with no AI draft, NOT an agent with no knowledge base. A real agent
     without this tool still has the KB; they just don't have a system
     doing the retrieval and first-draft writing for them.
  2. Then shows the REAL AI draft for that same ticket and times how long
     it takes you to review it — approve as-is, edit it, or reject it
     outright.

Everything is timed server-side (wall-clock from prompt-shown to
submit-received), not self-reported, and every raw per-ticket result is
written to disk so BENCHMARKS.md can be built from the real file, not from
whatever you remember afterward.

Usage:
    uv run python -m app.scripts.benchmark_manual_vs_assisted [N]
(N defaults to 20, not the full time-to-draft batch — BUILD_SPEC.md asks
 for 20-30 tickets, and this is real time you personally spend typing
 replies twice per ticket, so the default sits at the low end of that
 range. Pass a number explicitly to do more or fewer.)

Type your multi-line answer, then a line containing only ###END### to
submit it. For the AI-draft review step, you can also just type APPROVE
or REJECT on their own as a one-line answer instead of writing anything.
"""

import asyncio
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import select

from app.db.base import SessionLocal
from app.models.ticket import Ticket
from app.models.ticket_draft import TicketDraft

TIME_TO_DRAFT_RESULTS = Path(__file__).parent.parent / "ml" / "artifacts" / "benchmark_time_to_draft.json"
OUT_PATH = Path(__file__).parent.parent / "ml" / "artifacts" / "benchmark_manual_vs_assisted.json"
END_SENTINEL = "###END###"
DEFAULT_CAP = 20  # per BUILD_SPEC.md: "20-30 tickets", capped low end given this is YOUR real time


def _read_multiline(prompt: str) -> tuple[str, float]:
    print(prompt)
    print(f"(end with a line containing only {END_SENTINEL})")
    start = time.monotonic()
    lines = []
    for line in sys.stdin:
        if line.strip() == END_SENTINEL:
            break
        lines.append(line.rstrip("\n"))
    elapsed = time.monotonic() - start
    return "\n".join(lines).strip(), elapsed


async def _load_candidate_ticket_ids(n: int) -> list[uuid.UUID]:
    if not TIME_TO_DRAFT_RESULTS.exists():
        print(
            f"No {TIME_TO_DRAFT_RESULTS} found - run "
            "`uv run python -m app.scripts.benchmark_time_to_draft` first, "
            "so this can reuse those real tickets/drafts instead of running "
            "the pipeline again."
        )
        sys.exit(1)
    data = json.loads(TIME_TO_DRAFT_RESULTS.read_text())
    ids = [uuid.UUID(r["ticket_id"]) for r in data["per_ticket"] if not r["timed_out"]]
    return ids[:n]


async def run(n: int) -> None:
    ticket_ids = await _load_candidate_ticket_ids(n)
    print(f"Loaded {len(ticket_ids)} real tickets with real drafts.\n")

    results = []
    async with SessionLocal() as db:
        for i, tid in enumerate(ticket_ids, 1):
            ticket = await db.get(Ticket, tid)
            draft = (
                await db.execute(
                    select(TicketDraft).where(TicketDraft.ticket_id == tid).order_by(TicketDraft.created_at.desc())
                )
            ).scalars().first()
            if ticket is None or draft is None:
                continue

            print(f"\n{'=' * 70}\nTicket {i}/{len(ticket_ids)}  (category: {ticket.category})\n{'=' * 70}")
            print(f"\nCustomer message:\n{ticket.raw_text}\n")

            manual_text, manual_seconds = _read_multiline(
                "STEP 1 - MANUAL: this simulates an agent with NO AI draft, not an agent "
                "with no knowledge base. Open backend/app/kb/articles/ (25 .md files, named "
                "by category) in another window, search/skim for the relevant article the "
                "same way a real agent would, then write your reply from what you find there."
            )

            print(f"\n(manual step took {manual_seconds:.1f}s)\n")
            print(f"STEP 2 - ASSISTED: here is the real AI draft (confidence {draft.confidence:.2f}):\n")
            print(draft.draft_text)
            print()

            assisted_text, assisted_seconds = _read_multiline(
                "Type APPROVE if this is good as-is, REJECT if it's unusable, "
                "or your edited version of it."
            )

            stripped = assisted_text.strip().upper()
            if stripped == "APPROVE":
                action = "approved"
                edit_distance = 0.0
            elif stripped == "REJECT":
                action = "rejected"
                edit_distance = 1.0
            else:
                action = "edited"
                edit_distance = 1 - SequenceMatcher(None, draft.draft_text, assisted_text).ratio()

            print(f"(assisted step took {assisted_seconds:.1f}s, action={action})")

            results.append(
                {
                    "ticket_id": str(tid),
                    "manual_seconds": round(manual_seconds, 1),
                    "manual_reply_chars": len(manual_text),
                    "assisted_seconds": round(assisted_seconds, 1),
                    "action": action,
                    "edit_distance": round(edit_distance, 3),
                }
            )

    if not results:
        print("No results recorded.")
        return

    manual_times = sorted(r["manual_seconds"] for r in results)
    assisted_times = sorted(r["assisted_seconds"] for r in results)

    def _median(xs):
        n_ = len(xs)
        return xs[n_ // 2] if n_ % 2 else (xs[n_ // 2 - 1] + xs[n_ // 2]) / 2

    approved = sum(1 for r in results if r["action"] == "approved")
    edited = sum(1 for r in results if r["action"] == "edited")
    rejected = sum(1 for r in results if r["action"] == "rejected")

    summary = {
        "n": len(results),
        "manual_median_seconds": round(_median(manual_times), 1),
        "assisted_median_seconds": round(_median(assisted_times), 1),
        "manual_total_seconds": round(sum(manual_times), 1),
        "assisted_total_seconds": round(sum(assisted_times), 1),
        "approved_as_is_pct": round(100 * approved / len(results), 1),
        "lightly_edited_pct": round(100 * edited / len(results), 1),
        "rejected_pct": round(100 * rejected / len(results), 1),
    }

    print(f"\n{'=' * 70}\nSUMMARY (n={summary['n']})\n{'=' * 70}")
    print(f"Manual median:   {summary['manual_median_seconds']}s")
    print(f"Assisted median: {summary['assisted_median_seconds']}s")
    print(f"Approved as-is:  {summary['approved_as_is_pct']}%")
    print(f"Lightly edited:  {summary['lightly_edited_pct']}%")
    print(f"Rejected:        {summary['rejected_pct']}%")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as f:
        json.dump(
            {"measured_at": datetime.now(timezone.utc).isoformat(), "per_ticket": results, "summary": summary},
            f,
            indent=2,
        )
    print(f"\nWrote {OUT_PATH}")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CAP
    asyncio.run(run(n))
