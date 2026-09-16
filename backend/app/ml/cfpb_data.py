"""Real training data: the CFPB Consumer Complaint Database.

Replaces the template-generated synthetic classifier data (app/ml/data.py),
which produced a meaningless 1.000 held-out accuracy because train/test
rows drawn from the same template shared their phrasing skeleton.

Source: https://www.consumerfinance.gov/data-research/consumer-complaints/
A public US government dataset of real consumer complaints against banks,
card issuers, lenders and money-transfer services — ~17.6M complaints, of
which ~3.8M have a free-text narrative. Narratives arrive already
PII-scrubbed by the CFPB (names/dates appear as `XXXX` / `XX/XX/XXXX`).

CFPB has no notion of "urgency" and no clean "refund" issue, so this
covers the CATEGORY label only. See DATA.md for what's real vs synthetic.

    uv run python -m app.ml.cfpb_data          # fetch + cache
    uv run python -m app.ml.cfpb_data --stats  # summarise the cache
"""

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

API = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
CACHE_PATH = Path(__file__).parent / "artifacts" / "cfpb_complaints.jsonl"

# Target rows per category. Categories whose issues genuinely don't have
# this many narratives just come back smaller — see the honest counts in
# DATA.md rather than padding them out.
PER_CATEGORY = 2000

# Rows requested per issue in a single call. The API's offset parameters
# (`frm`/`from`/`offset`/`page`) are all silently ignored — every page
# returns the same first N rows — and `search_after` rejects every cursor
# format tried. A large `size` in ONE request is the only pagination that
# actually works, and it returns all-unique rows up to at least 5000.
MAX_SIZE_PER_REQUEST = 3000

# --------------------------------------------------------------------------
# Mapping: CFPB `issue` -> ResolveIQ category.
#
# Deliberately keyed on `issue` rather than `product`: product describes
# which financial instrument is involved (credit card, mortgage), while
# issue describes what actually went wrong, which is what ResolveIQ's
# categories are about. Only issues that map unambiguously are included —
# broad ones like "Managing an account" are left out rather than forced
# into a bucket they only half fit.
# --------------------------------------------------------------------------
ISSUE_TO_CATEGORY: dict[str, str] = {
    # --- payment_failure: a payment didn't go through / went wrong -------
    "Trouble during payment process": "payment_failure",
    "Problem when making payments": "payment_failure",
    "Loan payment wasn't credited to your account": "payment_failure",
    "Payment to acct not credited": "payment_failure",
    "Money was taken from your bank account on the wrong day or for the wrong amount": "payment_failure",
    "Problem adding money": "payment_failure",
    "Problem caused by your funds being low": "payment_failure",
    # --- refund_delay: money owed back hasn't arrived --------------------
    # CFPB's weakest overlap with our taxonomy — see DATA.md.
    "Money was not available when promised": "refund_delay",
    "Was approved for a loan, but didn't receive the money": "refund_delay",
    "Was approved for a loan, but didn't receive money": "refund_delay",
    "Applied for loan/did not receive money": "refund_delay",
    "Lost or stolen refund": "refund_delay",
    "Lost or stolen money order": "refund_delay",
    # --- account_lock: can't access / account closed or frozen -----------
    "Closing an account": "account_lock",
    "Closing your account": "account_lock",
    "Closing/Cancelling account": "account_lock",
    "Trouble accessing funds in your mobile or digital wallet": "account_lock",
    "Problem with fraud alerts or security freezes": "account_lock",
    "Problem getting a card or closing an account": "account_lock",
    "Managing, opening, or closing your mobile wallet account": "account_lock",
    # --- dispute: contesting a charge / unauthorised / fraud -------------
    "Problem with a purchase shown on your statement": "dispute",
    "Fraud or scam": "dispute",
    "Unauthorized transactions or other transaction problem": "dispute",
    "Billing disputes": "dispute",
    "Identity theft / Fraud / Embezzlement": "dispute",
    "Unauthorized transactions/trans. issues": "dispute",
    "Unauthorized withdrawals or charges": "dispute",
    "Collection debt dispute": "dispute",
    # --- general_query: fees, statements, disclosures --------------------
    "Fees or interest": "general_query",
    "Charged fees or interest you didn't expect": "general_query",
    "Charged fees or interest I didn't expect": "general_query",
    "Unexpected or other fees": "general_query",
    "Confusing or missing disclosures": "general_query",
    "Billing statement": "general_query",
    "Late fee": "general_query",
    "Other fee": "general_query",
    "Charged upfront or unexpected fees": "general_query",
    "Excessive fees": "general_query",
}

CATEGORIES = sorted(set(ISSUE_TO_CATEGORY.values()))


@dataclass(frozen=True)
class Complaint:
    complaint_id: str
    text: str
    category: str
    issue: str
    product: str


def _issues_for(category: str) -> list[str]:
    return [i for i, c in ISSUE_TO_CATEGORY.items() if c == category]


def _fetch_issue(client: httpx.Client, issue: str, want: int) -> list[Complaint]:
    """Fetches narratives for one CFPB issue in a single request.

    The label comes from each row's OWN `issue` field, never from the issue
    we asked for — if the server-side filter ever returns something off, the
    row is dropped rather than silently mislabelled. Mislabelled training
    data is the single most expensive failure mode here, so this stays
    defensive even though the filter currently behaves.
    """
    params = {
        "size": str(min(want, MAX_SIZE_PER_REQUEST)),
        "has_narrative": "true",
        "issue": issue,
        "no_aggs": "true",
    }
    try:
        r = client.get(API, params=params, timeout=180)
        r.raise_for_status()
    except Exception as exc:
        print(f"      ! {type(exc).__name__} fetching {issue!r}, skipping")
        return []

    out: list[Complaint] = []
    mislabelled = 0
    for h in r.json().get("hits", {}).get("hits", []):
        src = h["_source"]
        actual_issue = src.get("issue")
        if actual_issue != issue:
            mislabelled += 1
            continue
        text = (src.get("complaint_what_happened") or "").strip()
        if len(text) < 50:  # skip stubs — nothing to learn from
            continue
        out.append(
            Complaint(
                complaint_id=str(src.get("complaint_id")),
                text=text,
                category=ISSUE_TO_CATEGORY[actual_issue],
                issue=actual_issue,
                product=src.get("product", ""),
            )
        )

    if mislabelled:
        print(f"      ! dropped {mislabelled} row(s) whose issue != {issue!r}")
    time.sleep(0.2)  # be polite to a public government API
    return out


def fetch_all(per_category: int = PER_CATEGORY) -> list[Complaint]:
    collected: list[Complaint] = []
    seen_ids: set[str] = set()

    with httpx.Client(headers={"User-Agent": "ResolveIQ/research"}) as client:
        for category in CATEGORIES:
            issues = _issues_for(category)
            per_issue = max(1, per_category // len(issues))
            got: list[Complaint] = []
            print(f"  {category}: {len(issues)} issue(s), targeting {per_category}")

            for issue in issues:
                if len(got) >= per_category:
                    break
                # Ask each issue for an even share, but request extra headroom
                # so that issues with plenty of data can cover for the small
                # ones. No second pass — re-requesting the same issue returns
                # the same rows (the API ignores every offset parameter), so
                # a top-up loop would only produce duplicates.
                rows = _fetch_issue(client, issue, min(per_issue * 3, per_category))

                added = 0
                for c in rows:
                    if len(got) >= per_category:
                        break
                    # Add to the seen set as we go — filtering the batch
                    # against `seen_ids` before adding lets duplicates
                    # *within* one batch slip through.
                    if c.complaint_id in seen_ids:
                        continue
                    seen_ids.add(c.complaint_id)
                    got.append(c)
                    added += 1
                print(f"      {added:>5} from {issue!r}  (of {len(rows)} available)")

            print(f"    -> {len(got)} collected for {category}")
            collected.extend(got)

    return collected


def save(complaints: list[Complaint]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CACHE_PATH.open("w", encoding="utf-8") as f:
        for c in complaints:
            f.write(
                json.dumps(
                    {
                        "complaint_id": c.complaint_id,
                        "text": c.text,
                        "category": c.category,
                        "issue": c.issue,
                        "product": c.product,
                    }
                )
                + "\n"
            )


def load() -> list[Complaint]:
    if not CACHE_PATH.exists():
        raise FileNotFoundError(
            f"No CFPB cache at {CACHE_PATH}. Run `uv run python -m app.ml.cfpb_data` first."
        )
    out = []
    with CACHE_PATH.open(encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            out.append(Complaint(**d))
    return out


def _print_stats(complaints: list[Complaint]) -> None:
    from collections import Counter

    by_cat = Counter(c.category for c in complaints)
    print(f"\n{len(complaints)} complaints cached at {CACHE_PATH}")
    print(f"file size: {CACHE_PATH.stat().st_size / 1_000_000:.1f} MB")
    print("\nby category:")
    for cat, n in sorted(by_cat.items()):
        print(f"  {n:>6}  {cat}")
    lens = [len(c.text) for c in complaints]
    lens.sort()
    print(
        f"\nnarrative length (chars): "
        f"min {lens[0]}, median {lens[len(lens) // 2]}, max {lens[-1]}"
    )


def main() -> None:
    if "--stats" in sys.argv:
        _print_stats(load())
        return

    print("Fetching CFPB complaint narratives...")
    complaints = fetch_all()
    save(complaints)
    _print_stats(complaints)


if __name__ == "__main__":
    main()
