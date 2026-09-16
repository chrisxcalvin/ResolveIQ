"""Phase 2 concurrency check — run against the LIVE stack, not hermetic.

Needs the API, Celery worker, Postgres, and Redis actually running. This
is deliberately not a pytest test: it's an operational check against real
running infrastructure, the same way you'd load-test a deployed service,
not a unit of application logic.

Two things, in order:

1. Fires N ticket submissions genuinely simultaneously (asyncio.gather,
   not a loop) and confirms every one is accepted, reaches a terminal
   pipeline status, and gets a unique id — no drops, no corruption.
2. Takes one of those now-drafted tickets and fires N simultaneous resolve
   requests at it (alternating approve/escalate), confirming exactly one
   wins (200) and the rest are cleanly rejected (409) — the real test of
   the `SELECT ... FOR UPDATE` lock in resolve_ticket, not just its status
   check.

Usage:
    uv run python -m tests.concurrency_check 10
"""

import asyncio
import sys
import time

import httpx

BASE = "http://127.0.0.1:8000"
POLL_TIMEOUT_S = 90


async def login(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{BASE}/auth/login",
        json={"email": "demo@resolveiq.io", "password": "resolveiq-demo"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


async def submit_one(client: httpx.AsyncClient, token: str, i: int) -> dict:
    payload = {
        "customer_masked_identifier": f"cust_concurrency_{i}",
        "channel": "email",
        "raw_text": (
            f"[concurrency check #{i}] My payment failed but the charge "
            f"still shows pending on my statement, was I actually charged?"
        ),
    }
    r = await client.post(
        f"{BASE}/tickets", json=payload, headers={"Authorization": f"Bearer {token}"}
    )
    if r.status_code != 201:
        return {"i": i, "error": f"HTTP {r.status_code}: {r.text[:200]}"}
    return {"i": i, "id": r.json()["id"]}


async def poll_until_terminal(client: httpx.AsyncClient, token: str, ticket_id: str) -> dict:
    start = time.monotonic()
    while time.monotonic() - start < POLL_TIMEOUT_S:
        r = await client.get(
            f"{BASE}/tickets/{ticket_id}", headers={"Authorization": f"Bearer {token}"}
        )
        if r.status_code != 200:
            return {"id": ticket_id, "poll_error": f"HTTP {r.status_code}"}
        d = r.json()
        if d["status"] in ("drafted", "resolved", "escalated"):
            return {
                "id": ticket_id,
                "final_status": d["status"],
                "seconds_to_terminal": round(time.monotonic() - start, 1),
            }
        await asyncio.sleep(1.5)
    return {"id": ticket_id, "timed_out": True}


async def resolve(client: httpx.AsyncClient, token: str, ticket_id: str, action: str) -> dict:
    r = await client.post(
        f"{BASE}/tickets/{ticket_id}/resolve",
        json={"action": action, "escalation_note": "concurrency check" if action == "escalate" else None},
        headers={"Authorization": f"Bearer {token}"},
    )
    return {"action": action, "status_code": r.status_code}


async def check_submission_burst(client: httpx.AsyncClient, token: str, n: int) -> list[dict]:
    print(f"1) Firing {n} ticket submissions SIMULTANEOUSLY...")
    t0 = time.monotonic()
    submit_results = await asyncio.gather(*[submit_one(client, token, i) for i in range(n)])
    submit_s = time.monotonic() - t0

    errors = [r for r in submit_results if "error" in r]
    ok = [r for r in submit_results if "id" in r]
    print(f"   {len(ok)}/{n} accepted in {submit_s:.2f}s, {len(errors)} error(s)")
    for r in errors:
        print(f"     ! {r}")
    if errors:
        raise SystemExit("Submission errors — stopping, nothing further is meaningful.")

    unique_ids = {r["id"] for r in ok}
    if len(unique_ids) != len(ok):
        raise SystemExit(f"ID COLLISION: {len(ok)} submissions, only {len(unique_ids)} unique ids.")

    print(f"   Polling all {n} until terminal...")
    t1 = time.monotonic()
    poll_results = await asyncio.gather(
        *[poll_until_terminal(client, token, r["id"]) for r in ok]
    )
    poll_s = time.monotonic() - t1

    timed_out = [r for r in poll_results if r.get("timed_out")]
    print(f"   All resolved to a terminal status in {poll_s:.1f}s, {len(timed_out)} timed out")
    if timed_out:
        raise SystemExit(f"{len(timed_out)} ticket(s) never reached a terminal status.")

    print("   PASS — no drops, no id collisions, all reached a terminal status.\n")
    return ok


async def check_concurrent_resolve(client: httpx.AsyncClient, token: str, ticket_id: str, n: int) -> None:
    print(f"2) Firing {n} simultaneous resolve requests at ticket {ticket_id}...")
    actions = ["approve" if i % 2 == 0 else "escalate" for i in range(n)]
    results = await asyncio.gather(*[resolve(client, token, ticket_id, a) for a in actions])

    successes = [r for r in results if r["status_code"] == 200]
    conflicts = [r for r in results if r["status_code"] == 409]
    other = [r for r in results if r["status_code"] not in (200, 409)]

    print(f"   200 OK: {len(successes)}  |  409 Conflict: {len(conflicts)}  |  other: {len(other)}")
    if other:
        for r in other:
            print(f"     ! unexpected: {r}")
        raise SystemExit("Unexpected status code(s) — see above.")
    if len(successes) != 1 or len(conflicts) != n - 1:
        raise SystemExit(
            f"FAIL — expected exactly 1 success and {n - 1} conflicts, "
            f"got {len(successes)} success(es) and {len(conflicts)} conflict(s)."
        )

    print("   PASS — exactly one request won the lock, all others were cleanly rejected.\n")


async def main(n: int) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        token = await login(client)

        submitted = await check_submission_burst(client, token, n)
        await check_concurrent_resolve(client, token, submitted[0]["id"], n)

    print("All concurrency checks passed.")


if __name__ == "__main__":
    n_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    asyncio.run(main(n_arg))
