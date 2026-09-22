"""Decision agent: confidence + urgency + category -> routing metadata.

Per the PRD ("a human always approves, edits, or escalates"), this never
auto-sends anything for any category by default — it only decides how a
ticket is surfaced to the reviewing agent: a normal reviewable draft, one
flagged for specialist attention, or (Phase 7) one flagged as fast-path
eligible for one-click approval. `dispute` + high urgency is the closest
proxy available, given the current category set, for the PRD's "fraud,
large refunds" high-risk language.

`needs_review` is unconditionally True everywhere in this file except the
one `auto_resolved` branch, which only fires when `settings.auto_resolve_threshold`
is explicitly set (off by default) — see docs/checkpoints/phase-7.md for
why that's a narrow, deliberately opt-in exception to the PRD's invariant,
not a general auto-send path.
"""

from dataclasses import dataclass

LOW_CONFIDENCE_THRESHOLD = 0.35
HIGH_URGENCY_THRESHOLD = 0.75
SPECIALIST_CATEGORIES = {"dispute"}

# Fast-path: the category taxonomy has no clean FAQ-vs-account-specific
# split (every category mixes both), so eligibility leans on the signals
# that actually separate them — a generic, low-urgency question the
# knowledge base answers tightly and the classifier is sure about, not a
# specific account/transaction lookup.
FAST_PATH_MAX_URGENCY = 0.4
FAST_PATH_MIN_CONFIDENCE = 0.7
FAST_PATH_MIN_RETRIEVAL_SIMILARITY = 0.7


@dataclass(frozen=True)
class Decision:
    needs_review: bool
    specialist_flagged: bool
    fast_path_eligible: bool
    auto_resolved: bool
    reason: str


def _is_fast_path_eligible(category: str, urgency_score: float, confidence: float, avg_retrieval_similarity: float | None) -> bool:
    return (
        category not in SPECIALIST_CATEGORIES
        and urgency_score < FAST_PATH_MAX_URGENCY
        and confidence >= FAST_PATH_MIN_CONFIDENCE
        and avg_retrieval_similarity is not None
        and avg_retrieval_similarity >= FAST_PATH_MIN_RETRIEVAL_SIMILARITY
    )


def decide(
    category: str,
    urgency_score: float,
    confidence: float,
    avg_retrieval_similarity: float | None = None,
    auto_resolve_threshold: float | None = None,
) -> Decision:
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return Decision(
            needs_review=True,
            specialist_flagged=True,
            fast_path_eligible=False,
            auto_resolved=False,
            reason=f"Low draft confidence ({confidence:.2f}) — needs careful human review.",
        )

    if category in SPECIALIST_CATEGORIES and urgency_score >= HIGH_URGENCY_THRESHOLD:
        return Decision(
            needs_review=True,
            specialist_flagged=True,
            fast_path_eligible=False,
            auto_resolved=False,
            reason=f"High-urgency {category} ticket — routed for specialist attention.",
        )

    fast_path = _is_fast_path_eligible(category, urgency_score, confidence, avg_retrieval_similarity)

    if fast_path and auto_resolve_threshold is not None and confidence >= auto_resolve_threshold:
        return Decision(
            needs_review=False,
            specialist_flagged=False,
            fast_path_eligible=True,
            auto_resolved=True,
            reason=(
                f"Auto-resolved: confidence ({confidence:.2f}) cleared the configured "
                f"threshold ({auto_resolve_threshold:.2f}) on a non-account-specific, "
                "tightly-matched FAQ answer."
            ),
        )

    if fast_path:
        return Decision(
            needs_review=True,
            specialist_flagged=False,
            fast_path_eligible=True,
            auto_resolved=False,
            reason="High-confidence FAQ match — flagged for one-click approval.",
        )

    return Decision(
        needs_review=True,
        specialist_flagged=False,
        fast_path_eligible=False,
        auto_resolved=False,
        reason="Standard review — draft ready for agent approval.",
    )
