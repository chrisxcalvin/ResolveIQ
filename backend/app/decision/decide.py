"""Decision agent: confidence + urgency + category -> routing metadata.

Per the PRD ("a human always approves, edits, or escalates"), this never
auto-sends anything for any category — it only decides how a ticket is
surfaced to the reviewing agent: a normal reviewable draft, or one flagged
for specialist attention. `dispute` + high urgency is the closest proxy
available, given the current category set, for the PRD's "fraud, large
refunds" high-risk language.
"""

from dataclasses import dataclass

LOW_CONFIDENCE_THRESHOLD = 0.35
HIGH_URGENCY_THRESHOLD = 0.75
SPECIALIST_CATEGORIES = {"dispute"}


@dataclass(frozen=True)
class Decision:
    needs_review: bool
    specialist_flagged: bool
    reason: str


def decide(category: str, urgency_score: float, confidence: float) -> Decision:
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return Decision(
            needs_review=True,
            specialist_flagged=True,
            reason=f"Low draft confidence ({confidence:.2f}) — needs careful human review.",
        )

    if category in SPECIALIST_CATEGORIES and urgency_score >= HIGH_URGENCY_THRESHOLD:
        return Decision(
            needs_review=True,
            specialist_flagged=True,
            reason=f"High-urgency {category} ticket — routed for specialist attention.",
        )

    return Decision(
        needs_review=True,
        specialist_flagged=False,
        reason="Standard review — draft ready for agent approval.",
    )
